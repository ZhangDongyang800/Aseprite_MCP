"""The v2 tool surface (spec §5)."""

from pathlib import Path
from typing import Optional

from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image

import src.v2.ops  # noqa: F401  triggers registration of the built-in ops
from src.v2.executor import Engine
from src.v2.registry import REGISTRY
from src.v2.result import Envelope, ErrorCode


def _inside_work_dir(path: str, work_dir: Path) -> bool:
    """True when *path* lives under the server's work directory."""
    try:
        Path(path).resolve().relative_to(Path(work_dir).resolve())
        return True
    except (ValueError, OSError):
        return False


def _discard(session_manager, session_id: Optional[str]) -> None:
    try:
        if session_id:
            session_manager.close_session(session_id)
    except KeyError:
        pass


def _refresh_canvas_info(session_manager, session_id, first_op: str, env: Envelope) -> None:
    """Keep aseprite://canvas/<id>/info honest about the document that is really loaded.

    The session is provisioned before the batch runs, so its placeholder size is stale the
    moment open_sprite learns the real dimensions; resources and sessions list must not keep
    advertising 1x1.
    """
    if not session_id or first_op not in ("create_sprite", "open_sprite"):
        return
    for result in env.op_results:
        data = result.data if isinstance(result.data, dict) else {}
        width, height = data.get("width"), data.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            session_manager.update_canvas_info(session_id, width=width, height=height)
            return


def register_v2_tools(mcp, session_manager, runner, config):
    engine = Engine(session_manager, runner, config)

    @mcp.tool(output_schema=None, annotations={"destructiveHint": True, "openWorldHint": False})
    def apply_operations(
        ops: list[dict],
        session_id: Optional[str] = None,
        atomic: bool = True,
        dry_run: bool = False,
        confirmed: bool = False,
        verbose: bool = False,
    ) -> Envelope:
        """Run a batch of Aseprite operations (the only mutation entry point).

        When session_id is empty and the first op is create_sprite/open_sprite, a session
        is created before the batch runs. Destructive ops require confirmed=true.

        atomic=true (the default) rolls the whole batch back on failure; atomic=false keeps
        the ops that already succeeded, spells out pass/fail per entry in op_results, and
        adds a warning that this run was a partial success.

        paint_grid dofiles a Lua grid file: a file inside the server work directory runs
        as-is, a path outside it requires confirmed=true (the same gate as run_lua).

        On success op_results keeps only what the server learned at runtime (e.g. the real
        size open_sprite read); entries that merely echo the caller's params are dropped.
        Use verbose=true to get the full echo or the dry_run execution plan.
        """
        if not ops:
            return Envelope.failure(
                ErrorCode.INVALID_ARGS, "ops must be a non-empty list",
                session_id=session_id, mode=config.mode,
            )

        # Validate before creating a session: invalid params must not leak a work directory
        parsed, err = REGISTRY.validate(ops)
        if err is not None:
            return Envelope.failure(
                err.code, err.message, hint=err.hint, op_index=err.op_index,
                session_id=session_id, mode=config.mode,
            )

        # Confirmation gate before the session exists: a rejected batch must have no side
        # effects
        if not confirmed and any(spec.destructive for spec, _ in parsed):
            return Envelope.failure(
                ErrorCode.CONFIRMATION_REQUIRED,
                "batch contains destructive ops",
                hint="re-call with confirmed=true",
                session_id=session_id, mode=config.mode,
            )

        # paint_grid dofiles a Lua file: outside the server's own work dir that is arbitrary
        # code execution, which is what run_lua's double gate exists to control.
        if not confirmed:
            for spec, params in parsed:
                if spec.name != "paint_grid":
                    continue
                grid_path = getattr(params, "path", None)
                if grid_path and not _inside_work_dir(grid_path, config.work_dir):
                    return Envelope.failure(
                        ErrorCode.CONFIRMATION_REQUIRED,
                        "paint_grid loads a Lua file from outside the server work directory",
                        hint=(
                            "re-call with confirmed=true, or keep the grid file under the "
                            "session work directory"
                        ),
                        session_id=session_id, mode=config.mode,
                    )

        # undo/redo are meta ops: routed to the engine only as a single-op batch (no Lua
        # is generated)
        meta = {spec.name for spec, _ in parsed} & {"undo", "redo"}
        if meta:
            if len(parsed) != 1:
                return Envelope.failure(
                    ErrorCode.INVALID_ARGS,
                    "undo/redo cannot be combined with other ops",
                    hint="undo/redo must be a single-op batch",
                    session_id=session_id, mode=config.mode,
                )
            if not dry_run:
                if session_id is None:
                    return engine._missing(session_id)
                if parsed[0][0].name == "undo":
                    return engine.undo(session_id)
                return engine.redo(session_id)

        first_spec, first_params = parsed[0]
        auto_created = False
        if not dry_run and session_id is None and first_spec.name in ("create_sprite", "open_sprite"):
            # Session metadata comes from the validated params, never from the raw caller's
            # dict: values like "16.0" survive op validation but would blow up int().
            width = int(getattr(first_params, "width", 1) or 1)
            height = int(getattr(first_params, "height", 1) or 1)
            color_mode = str(getattr(first_params, "color_mode", None) or "rgb")
            session_id = session_manager.create_session(
                width=width, height=height, color_mode=color_mode,
            )
            auto_created = True
            ops = [dict(o) for o in ops]
            ops[0]["file"] = str(session_manager.get_ase_path(session_id))

        env = engine.apply(session_id, ops, atomic=atomic, dry_run=dry_run, verbose=verbose)

        if not dry_run and env.ok:
            _refresh_canvas_info(session_manager, session_id, first_spec.name, env)
        elif not dry_run and auto_created and not env.ok:
            # A provisioned session whose first op failed is an orphan nobody will ever use;
            # leaving it behind only pollutes aseprite://sessions until the sweeper runs.
            _discard(session_manager, session_id)

        if env.ok and not dry_run and any(spec.name == "close_session" for spec, _ in parsed):
            if session_id:
                session_manager.close_session(session_id)
        return env

    @mcp.tool(output_schema=None, annotations={"destructiveHint": True, "openWorldHint": False})
    def run_lua(
        session_id: str,
        code: str,
        unsafe: bool = False,
        confirmed: bool = False,
    ) -> Envelope:
        """Run arbitrary Lua (escape hatch). Requires unsafe=true and confirmed=true.

        In CLI mode the snippet gets the same snapshot protection as an op batch: a failing
        snippet rolls the document back, a successful one keeps the pre-change state as the
        undo backup. Live (ws) mode has no file snapshot, so whether a failed snippet can be
        rolled back depends on Aseprite transactions being available; the failure envelope
        says so.
        In CLI mode every call rewrites the .ase, so changed means "the document was
        rewritten", not "the content changed semantically".
        """
        if not unsafe:
            return Envelope.failure(
                ErrorCode.UNSAFE_REQUIRED,
                "run_lua requires unsafe=true",
                hint="prefer apply_operations; run_lua can break documents",
                session_id=session_id, mode=config.mode,
            )
        if not confirmed:
            return Envelope.failure(
                ErrorCode.CONFIRMATION_REQUIRED,
                "run_lua requires confirmed=true",
                hint="re-call with confirmed=true",
                session_id=session_id, mode=config.mode,
            )
        return engine.run_lua(session_id, code)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def inspect(
        session_id: str,
        scale: int = 4,
        view: str = "composite",
        frame: int = 1,
    ) -> ToolResult:
        """Return a canvas preview plus quantitative metrics (read-only; never edits).

        For animated documents, frame (1-based) picks which frame to look at; out-of-range
        values are clamped on the Lua side.
        """
        import json

        from src.v2.inspect import compute_metrics

        try:
            work = session_manager.get_work_dir(session_id)
            ase = session_manager.get_ase_path(session_id)
        except KeyError:
            message = f"session not found: {session_id}"
            return ToolResult(
                content=[message],
                structured_content={
                    "ok": False,
                    "error": {"code": "session_not_found", "message": message},
                },
                is_error=True,
            )

        png = work / "preview.png"
        metrics_png = work / "metrics_src.png"
        with engine.session_lock(session_id):
            result = runner.run_script("inspect.lua", {
                "file": str(ase), "output": str(png),
                "metrics_output": str(metrics_png),
                "scale": str(scale), "view": view, "frame": str(frame),
            })
            if not result["success"]:
                message = result.get("error", "inspect failed")
                return ToolResult(
                    content=[message],
                    structured_content={
                        "ok": False,
                        "error": {"code": "script_error", "message": message},
                    },
                    is_error=True,
                )

            if not png.exists() or not metrics_png.exists():
                missing = ", ".join(
                    p.name for p in (png, metrics_png) if not p.exists()
                )
                message = f"inspect.lua reported success but wrote no {missing}"
                return ToolResult(
                    content=[message],
                    structured_content={
                        "ok": False,
                        "error": {"code": "file_error", "message": message},
                    },
                    is_error=True,
                )

            meta = json.loads(result["stdout"].strip().splitlines()[-1])
            metrics = compute_metrics(metrics_png, meta)
            (work / "metrics.json").write_text(
                json.dumps({"meta": meta, "metrics": metrics}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            image = Image(path=str(png))
        warnings: list[str] = []
        if meta.get("scale_clamped"):
            warnings.append(
                f"preview scaled to {meta.get('scale')}x instead of {scale}x to stay inside the "
                "preview size budget; the metrics are still exact, only the image is smaller"
            )
        return ToolResult(
            content=[image],
            structured_content={"ok": True, "meta": meta, "metrics": metrics,
                                **({"warnings": warnings} if warnings else {})},
        )

    return engine
