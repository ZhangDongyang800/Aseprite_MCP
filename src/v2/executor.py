"""执行器：锁、备份、编译、单进程执行（spec §6）。"""

import contextlib
import shutil
import threading
import time

from src.v2.compile import compile_ops, parse_result_stdout
from src.v2.registry import REGISTRY
from src.v2.result import (
    Artifact, Envelope, ErrorCode, OpResult, UndoInfo, script_diagnostics,
)

BACKUP_NAME = "undo_backup.ase"
REDO_NAME = "redo_backup.ase"
SNAPSHOT_NAME = "_batch_before.ase"
TRANSACTION_WARNING = "app.transaction unavailable; CLI atomicity enforced by file snapshot"


def _novelty(data, supplied: dict):
    """Drop result fields the caller already stated.

    The model wrote `supplied`, so echoing it back is pure token cost; only values the server
    learned at runtime (an opened file's real size, a resolved save path) are worth returning.
    """
    if not isinstance(data, dict):
        return data
    kept = {k: v for k, v in data.items() if supplied.get(k) != v}
    return kept or None


class Engine:
    def __init__(self, session_manager, runner, config):
        self.session_manager = session_manager
        self.runner = runner
        self.config = config
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    # ---------- public ----------

    @contextlib.contextmanager
    def session_lock(self, session_id: str):
        """公共每会话锁：run_lua 与 inspect 必须经此串行化。"""
        with self._lock(session_id):
            yield

    def apply(self, session_id, raw_ops, *, atomic=True, dry_run=False, verbose=False) -> Envelope:
        start = time.time()
        parsed, err = REGISTRY.validate(raw_ops)
        if err is not None:
            return Envelope.failure(
                err.code, err.message, hint=err.hint, op_index=err.op_index,
                session_id=session_id, mode=self.config.mode,
            )

        if dry_run:
            # A dry run's only news is the verdict; the plan is the caller's own input.
            results = []
            if verbose:
                results = [OpResult(op="plan", ok=True, data=[
                    {"op": spec.name, "params": params.model_dump(mode="json")}
                    for spec, params in parsed])]
            return Envelope(
                ok=True, session_id=session_id, mode=self.config.mode,
                op_results=results,
                changed=False,
                undo=UndoInfo(mode=self._undo_mode(), available=False),
                timing_ms=int((time.time() - start) * 1000),
            )

        with self._lock(session_id):
            return self._apply_locked(session_id, parsed, atomic, start)

    def run_lua(self, session_id, code: str) -> Envelope:
        """Run an arbitrary snippet with the same rollback as an op batch.

        Without the snapshot a snippet that added a frame or a tag left no way back short of
        reopening the session, and `changed` was asserted rather than observed.
        """
        start = time.time()
        try:
            work = self.session_manager.get_work_dir(session_id)
            path = self.session_manager.get_ase_path(session_id)
        except KeyError:
            return self._missing(session_id)

        snapshot = self.config.mode == "cli"
        before = work / SNAPSHOT_NAME
        with self.session_lock(session_id):
            if snapshot:
                (work / REDO_NAME).unlink(missing_ok=True)
                before.unlink(missing_ok=True)
                if path.exists():
                    shutil.copy2(path, before)
            stamp = path.stat().st_mtime_ns if path.exists() else None
            snippet = work / "_run_lua.lua"
            snippet.write_text(code, encoding="utf-8")
            result = self.runner.run_script("mcp_run_lua.lua", {
                "file": str(path), "code_path": str(snippet),
            })

        if not result["success"]:
            self._restore_snapshot(before, path)
            message, hint = script_diagnostics(result)
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR, message, hint=hint,
                session_id=session_id, mode=self.config.mode,
            )

        # The .ase writer is not byte-deterministic, so "changed" means "the document was
        # rewritten" here — exactly what the op batch reports.
        changed = not snapshot or (
            (path.stat().st_mtime_ns if path.exists() else None) != stamp
        )
        if snapshot:
            if changed:
                before.replace(work / BACKUP_NAME)
            else:
                before.unlink(missing_ok=True)
        return Envelope(
            ok=True, session_id=session_id, mode=self.config.mode,
            op_results=[OpResult(op="run_lua", ok=True,
                                 data={"stdout": result.get("stdout", "")})],
            changed=changed,
            undo=UndoInfo(mode=self._undo_mode(), available=changed),
            timing_ms=int((time.time() - start) * 1000),
        )

    def undo(self, session_id) -> Envelope:
        with self._lock(session_id):
            try:
                work = self.session_manager.get_work_dir(session_id)
                path = self.session_manager.get_ase_path(session_id)
            except KeyError:
                return self._missing(session_id)
            if self.config.mode != "cli":
                return self._native("undo", session_id)
            backup = work / BACKUP_NAME
            if not backup.exists():
                return Envelope.failure(
                    ErrorCode.NO_MORE_UNDO, "nothing to undo (no backup)",
                    session_id=session_id, mode=self.config.mode,
                )
            if path.exists():
                shutil.copy2(path, work / REDO_NAME)
            shutil.copy2(backup, path)
            backup.unlink()
            return self._ok(session_id, "undo")

    def redo(self, session_id) -> Envelope:
        with self._lock(session_id):
            try:
                work = self.session_manager.get_work_dir(session_id)
                path = self.session_manager.get_ase_path(session_id)
            except KeyError:
                return self._missing(session_id)
            redo_backup = work / REDO_NAME
            if self.config.mode == "cli" and not redo_backup.exists():
                return Envelope.failure(
                    ErrorCode.NO_MORE_REDO, "nothing to redo",
                    session_id=session_id, mode=self.config.mode,
                )
            if self.config.mode == "cli":
                if path.exists():
                    shutil.copy2(path, work / BACKUP_NAME)
                shutil.copy2(redo_backup, path)
                redo_backup.unlink()
                return self._ok(session_id, "redo")
            return self._native("redo", session_id)

    # ---------- internals ----------

    def _undo_mode(self) -> str:
        return "file_backup" if self.config.mode == "cli" else "transaction"

    def _missing(self, session_id) -> Envelope:
        return Envelope.failure(
            ErrorCode.SESSION_NOT_FOUND, f"session not found: {session_id}",
            session_id=session_id, mode=self.config.mode,
        )

    def _ok(self, session_id, action: str) -> Envelope:
        return Envelope(
            ok=True, session_id=session_id, mode=self.config.mode,
            op_results=[OpResult(op=action, ok=True)],
            changed=True,
            undo=UndoInfo(mode=self._undo_mode(), available=True),
        )

    def _native(self, action: str, session_id) -> Envelope:
        result = self.runner.run_script(f"{action}.lua", {
            "file": str(self.session_manager.get_ase_path(session_id)),
        })
        if not result["success"]:
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR,
                result.get("error", f"{action} failed"),
                session_id=session_id, mode=self.config.mode,
            )
        stdout = (result.get("stdout") or "").strip()
        if not stdout.startswith("OK"):
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR,
                stdout or f"{action} produced no confirmation",
                hint="nothing to undo/redo, or Aseprite rejected the command",
                session_id=session_id, mode=self.config.mode,
            )
        return self._ok(session_id, action)

    def _apply_locked(self, session_id, parsed, atomic, start) -> Envelope:
        session = self.session_manager
        try:
            work = session.get_work_dir(session_id)
            path = session.get_ase_path(session_id)
        except KeyError:
            return self._missing(session_id)

        mutating = any(spec.mutating for spec, _ in parsed)
        snapshot = mutating and self.config.mode == "cli"
        before = work / SNAPSHOT_NAME
        if snapshot:
            # 新编辑清空 redo 栈（标准 undo 语义）；不覆盖 undo_backup，
            # 失败时用批前快照回滚，成功后才提升为 undo_backup。
            (work / REDO_NAME).unlink(missing_ok=True)
            before.unlink(missing_ok=True)
            if path.exists():
                shutil.copy2(path, before)

        lua_parsed = [(s, p) for s, p in parsed if s.lua]
        source = compile_ops(
            lua_parsed,
            file_path=path,
            scripts_dir=self.config.scripts_dir,
            atomic=atomic,
        )
        batch = work / "_batch.lua"
        batch.write_text(source, encoding="utf-8")

        result = self.runner.run_script_path(str(batch), {})
        if not result["success"]:
            self._restore_snapshot(before, path)
            message, hint = script_diagnostics(result)
            return Envelope.failure(
                ErrorCode.SCRIPT_ERROR, message, hint=hint,
                session_id=session_id, mode=self.config.mode,
            )
        try:
            payload = parse_result_stdout(result.get("stdout", ""))
        except ValueError as exc:
            self._restore_snapshot(before, path)
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR, str(exc),
                session_id=session_id, mode=self.config.mode,
            )

        reported = payload.get("ops", [])
        supplied = [p.model_dump(mode="json") for _, p in lua_parsed]
        failed = next((i for i, r in enumerate(reported) if not r.get("ok")), None)
        op_results = []
        for i, r in enumerate(reported):
            ok = bool(r.get("ok"))
            data = r.get("data")
            if ok:
                data = _novelty(data, supplied[i]) if i < len(supplied) else data
                if data is None:
                    continue
            op_results.append(OpResult(op=r.get("op", "?"), ok=ok, data=data))
        if failed is not None or payload.get("error"):
            self._restore_snapshot(before, path)
            env = Envelope.failure(
                ErrorCode.OP_FAILED,
                str(payload.get("error") or "op failed"),
                op_index=failed,
                session_id=session_id, mode=self.config.mode,
                op_results=op_results,
            )
            if snapshot and payload.get("transaction") is False:
                env.warnings.append(TRANSACTION_WARNING)
            return env

        if snapshot:
            if before.exists():
                before.replace(work / BACKUP_NAME)
        else:
            before.unlink(missing_ok=True)

        artifacts = self._collect_artifacts(payload)
        env = Envelope(
            ok=True, session_id=session_id, mode=self.config.mode,
            op_results=op_results,
            artifacts=artifacts,
            changed=bool(mutating and payload.get("saved")),
            undo=UndoInfo(mode=self._undo_mode(), available=mutating),
            timing_ms=int((time.time() - start) * 1000),
        )
        if payload.get("transaction") is False:
            env.warnings.append(TRANSACTION_WARNING)
        return env

    def _restore_snapshot(self, before, path) -> None:
        if before.exists():
            shutil.copy2(before, path)
            before.unlink()

    def _collect_artifacts(self, payload: dict) -> list[Artifact]:
        out: list[Artifact] = []
        for r in payload.get("ops", []):
            data = r.get("data") or {}
            if isinstance(data, dict) and data.get("artifact_path"):
                out.append(Artifact(
                    kind=data.get("artifact_kind", "png"),
                    path=data["artifact_path"],
                    role=data.get("artifact_role", r.get("op", "output")),
                ))
        return out
