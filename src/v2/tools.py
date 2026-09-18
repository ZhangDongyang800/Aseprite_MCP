"""v2 工具面（spec §5）。"""

from typing import Optional

from fastmcp.utilities.types import Image  # noqa: F401  (inspect 在 Task 2.2 使用)

import src.v2.ops  # noqa: F401  触发内置 op 注册
from src.v2.executor import Engine
from src.v2.registry import REGISTRY
from src.v2.result import Envelope, ErrorCode, OpResult


def register_v2_tools(mcp, session_manager, runner, config):
    engine = Engine(session_manager, runner, config)

    @mcp.tool(annotations={"destructiveHint": True, "openWorldHint": False})
    def apply_operations(
        ops: list[dict],
        session_id: Optional[str] = None,
        atomic: bool = True,
        dry_run: bool = False,
        confirmed: bool = False,
    ) -> Envelope:
        """执行一批 Aseprite 操作（唯一变更入口）。

        如果 session_id 为空且首个 op 是 create_sprite/open_sprite，
        会先创建会话再执行。destructive op 需要 confirmed=true。
        """
        if not ops:
            return Envelope.failure(
                ErrorCode.INVALID_ARGS, "ops must be a non-empty list",
                session_id=session_id, mode=config.mode,
            )

        # 先校验再建 session：参数不合法时不泄漏工作目录
        parsed, err = REGISTRY.validate(ops)
        if err is not None:
            return Envelope.failure(
                err.code, err.message, hint=err.hint, op_index=err.op_index,
                session_id=session_id, mode=config.mode,
            )

        # 确认门在建 session 之前：被拒的批量不得产生副作用
        if not confirmed and any(spec.destructive for spec, _ in parsed):
            return Envelope.failure(
                ErrorCode.CONFIRMATION_REQUIRED,
                "batch contains destructive ops",
                hint="re-call with confirmed=true",
                session_id=session_id, mode=config.mode,
            )

        first = ops[0].get("op") if isinstance(ops[0], dict) else None
        if not dry_run and session_id is None and first in ("create_sprite", "open_sprite"):
            session_id = session_manager.create_session(
                width=int(ops[0].get("width", 1)),
                height=int(ops[0].get("height", 1)),
                color_mode=str(ops[0].get("color_mode", "rgb")),
            )
            ops = [dict(o) for o in ops]
            ops[0]["file"] = str(session_manager.get_ase_path(session_id))

        env = engine.apply(session_id, ops, atomic=atomic, dry_run=dry_run)

        if env.ok and not dry_run and any(spec.name == "close_session" for spec, _ in parsed):
            if session_id:
                session_manager.close_session(session_id)
        return env

    @mcp.tool(annotations={"destructiveHint": True, "openWorldHint": False})
    def run_lua(
        session_id: str,
        code: str,
        unsafe: bool = False,
        confirmed: bool = False,
    ) -> Envelope:
        """执行任意 Lua（逃逸舱）。必须 unsafe=true 且 confirmed=true。"""
        if not unsafe:
            return Envelope.failure(
                ErrorCode.UNSUPPORTED_IN_MODE,
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
        try:
            work = session_manager.get_work_dir(session_id)
        except KeyError:
            return Envelope.failure(
                ErrorCode.SESSION_NOT_FOUND, f"session not found: {session_id}",
                session_id=session_id, mode=config.mode,
            )
        snippet = work / "_run_lua.lua"
        with engine.session_lock(session_id):
            snippet.write_text(code, encoding="utf-8")
            result = runner.run_script("mcp_run_lua.lua", {
                "file": str(session_manager.get_ase_path(session_id)),
                "code_path": str(snippet),
            })
        if not result["success"]:
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR,
                result.get("error", "run_lua failed"),
                hint=result.get("stderr", ""),
                session_id=session_id, mode=config.mode,
            )
        return Envelope(
            ok=True, session_id=session_id, mode=config.mode,
            op_results=[OpResult(op="run_lua", ok=True,
                                 data={"stdout": result.get("stdout", "")})],
            changed=True,
        )

    return engine
