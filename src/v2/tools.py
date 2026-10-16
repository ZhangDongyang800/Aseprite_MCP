"""v2 工具面（spec §5）。"""

from pathlib import Path
from typing import Optional

from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image

import src.v2.ops  # noqa: F401  触发内置 op 注册
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
        """执行一批 Aseprite 操作（唯一变更入口）。

        如果 session_id 为空且首个 op 是 create_sprite/open_sprite，
        会先创建会话再执行。destructive op 需要 confirmed=true。

        atomic=true（默认）失败即整体回滚；atomic=false 会保留已经成功的 op，
        在 op_results 里逐项标出成败，并在 warnings 里说明本次是部分成功。

        paint_grid 会 dofile 一个 Lua 网格文件：文件在服务器工作目录内可直接运行，
        指向工作目录之外的路径需要 confirmed=true（与 run_lua 同等级的门闩）。

        成功时 op_results 只保留服务器才知道的新信息（如 open_sprite 读到的实际尺寸），
        回显入参的条目会被丢弃；要完整回显或 dry_run 的执行计划就用 verbose=true。
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

        # undo/redo 是元 op：只在单 op 批量中路由到引擎（不生成 Lua）
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
        """执行任意 Lua（逃逸舱）。必须 unsafe=true 且 confirmed=true。

        CLI 模式下与 op 批量同样受快照保护：snippet 失败会回滚文档，成功则把改前状态留作
        undo 备份。Live(ws) 模式没有文件快照，snippet 失败能否回滚取决于 Aseprite 事务是否
        可用，失败信封里会说明。
        CLI 模式下每次调用都会重写 .ase，所以 changed 表示"文档被重写"而非"内容语义变化"。
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
        """返回画布预览与量化指标（只读，永不改动文档）。

        动画文档用 frame（1 起）指定看哪一帧；越界由 Lua 侧夹到有效范围。
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
