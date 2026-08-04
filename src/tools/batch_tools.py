"""批量编辑与逃逸舱工具：batch_edit, run_lua, undo, redo。

batch_edit 在单次 Aseprite 进程调用中执行多个操作（CLI 模式效率提升 N 倍）。
run_lua 提供完整的 Aseprite Lua API 访问（逃逸舱）。
undo/redo 支持（Live 模式用 app.command，CLI 模式用文件备份）。
"""

import json
import uuid
from pathlib import Path

from src.session import SessionManager
from src.tools.utils import (
    backup_ase_file, restore_ase_file,
    run_script_with_file, validate_session_id,
)


def register_batch_tools(mcp, session_manager: SessionManager, runner):
    """注册批量编辑与逃逸舱工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器（AsepriteRunner 或 WebSocketRunner）
    """

    @mcp.tool
    def batch_edit(session_id: str, operations: str) -> dict:
        """★推荐★ 在单次 Aseprite 调用中执行多个操作（效率提升 N 倍）。

        CLI 模式下每次工具调用都启动新 aseprite 进程，用本工具可将 N 个操作
        合并为 1 次进程调用。Live 模式下减少 WebSocket 往返次数。

        operations 格式: 以 ; 分隔的操作序列，每个操作格式为 "script_name k1=v1 k2=v2"。
        示例:
        "draw_rect x=0 y=0 width=8 height=8 color=#FF0000 filled=true ; fill_region x=1 y=1 color=#000000"

        可用脚本（所有 scripts/ 下的 Lua 脚本名）:
        draw_pixel, draw_line, draw_rect, draw_ellipse, fill_region, clear_region, clear_canvas,
        replace_color, invert_color, flip_canvas, rotate_canvas,
        add_frame, remove_frame, duplicate_frame, set_frame_duration,
        add_layer, remove_layer, duplicate_layer, merge_down, flatten,
        select_all, deselect, select_by_color, invert_selection, delete_selection,
        adjust_colors, apply_blur, draw_gradient

        Args:
            session_id: 会话 ID
            operations: 以 ; 分隔的操作序列
        """
        validate_session_id(session_id)

        if not operations or not operations.strip():
            return {"success": False, "error": "operations parameter is required"}

        # CLI 模式：备份当前文件（支持撤销）
        backup_ase_file(session_manager, session_id)

        ase_path = session_manager.get_ase_path(session_id)
        result = runner.run_script("batch_edit.lua", {
            "file": str(ase_path),
            "operations": operations.strip(),
        })

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Batch edit failed"),
                "stderr": result.get("stderr", ""),
            }

        # 解析批量结果
        try:
            data = json.loads(result["stdout"].strip())
            if "error" in data:
                # 脚本内部错误（如 JSON 解析失败）
                return {"success": False, "error": data["error"]}
            return {"success": True, **data}
        except json.JSONDecodeError:
            return {
                "success": True,
                "summary": result.get("stdout", "").strip(),
            }

    @mcp.tool
    def run_lua(session_id: str, code: str) -> dict:
        """在 Aseprite 中执行任意 Lua 代码（逃逸舱，完整 API 访问）。

        当某个功能未被现有工具覆盖时，直接用 Lua 代码操控 Aseprite。
        代码中可用变量: sprite（当前精灵）, app（Aseprite 应用对象），
        以及所有 _G._mcp_* 辅助函数。

        示例:
        -- 获取所有图层名
        for i, layer in ipairs(sprite.layers) do
            print(layer.name .. ": visible=" .. tostring(layer.isVisible))
        end

        -- 设置洋葱皮
        app.preferences.document(sprite).onionskin = {type = "mergin"}

        Args:
            session_id: 会话 ID
            code: 要执行的 Lua 代码
        """
        validate_session_id(session_id)

        if not code or not code.strip():
            return {"success": False, "error": "code parameter is required"}

        ase_path = session_manager.get_ase_path(session_id)

        result = runner.run_script("run_lua.lua", {
            "file": str(ase_path),
            "code": code.strip(),
        })

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Lua execution failed"),
                "stderr": result.get("stderr", ""),
            }

        stdout = result.get("stdout", "").strip()
        # 尝试解析 stdout 为 JSON，失败则返回原始字符串
        try:
            data = json.loads(stdout)
            if isinstance(data, dict) and "error" in data:
                return {"success": False, "error": data["error"], "stdout": data.get("stdout", "")}
            return {"success": True, "result": data}
        except json.JSONDecodeError:
            return {"success": True, "stdout": stdout}

    @mcp.tool
    def undo(session_id: str) -> dict:
        """撤销上一步操作。

        Live 模式: 使用 Aseprite 内置 Undo（app.command.Undo）。
        CLI 模式: 从 undo_backup.ase 恢复文件（仅能撤销最近一步）。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)

        ase_path = session_manager.get_ase_path(session_id)
        backup_path = ase_path.parent / "undo_backup.ase"
        if not backup_path.exists():
            return {"success": False, "error": "Nothing to undo (no backup found)"}

        # 尝试 Live 模式内置 Undo
        result = runner.run_script("undo.lua", {"file": str(ase_path)})
        if result["success"]:
            return {"success": True, "message": "Undo successful (Live mode)"}

        # CLI 模式：文件级恢复
        restored = restore_ase_file(session_manager, session_id)
        if restored:
            return {"success": True, "message": "Undo: restored from backup"}
        return {"success": False, "error": "Nothing to undo"}

    @mcp.tool
    def redo(session_id: str) -> dict:
        """重做已撤销的操作（仅在 Live 模式下有效）。

        CLI 模式的 undo 是文件级恢复，不支持 redo。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)

        ase_path = session_manager.get_ase_path(session_id)
        result = runner.run_script("redo.lua", {"file": str(ase_path)})
        if result["success"]:
            return {"success": True, "message": "Redo successful"}
        return {
            "success": False,
            "error": result.get("error", "Redo failed (may not be supported in CLI mode)"),
        }