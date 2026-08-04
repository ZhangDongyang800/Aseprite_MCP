"""选区工具：select_all, deselect, select_by_color, invert_selection, delete_selection。

Aseprite 的核心编辑范式是"选区 → 修改 → 取消选区"，这些工具补齐了该能力。
CLI 模式下选区通过文件持久化（跨进程），Live 模式下选区在 Aseprite 内存中持久。
"""

import json

from src.session import SessionManager
from src.tools.utils import (
    run_script_with_file, validate_color, validate_session_id,
)


def _get_sel_path(session_manager, session_id: str) -> str:
    """获取选区持久化文件路径。"""
    return str(session_manager.get_work_dir(session_id) / "selection.txt")


def register_selection_tools(mcp, session_manager: SessionManager, runner):
    """注册选区工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_sel_script(session_id: str, script_name: str, params: dict) -> dict:
        """执行选区脚本，自动注入 sel_path。"""
        return run_script_with_file(
            runner, session_manager, session_id, script_name,
            {**params, "sel_path": _get_sel_path(session_manager, session_id)},
            error_label="Selection operation failed",
        )

    @mcp.tool
    def select_all(session_id: str) -> dict:
        """全选画布（Ctrl+A 等效）。

        Args:
            session_id: 会话 ID
        """
        return _run_sel_script(session_id, "select_all.lua", {})

    @mcp.tool
    def deselect(session_id: str) -> dict:
        """取消当前选区（Ctrl+D 等效）。

        Args:
            session_id: 会话 ID
        """
        return _run_sel_script(session_id, "deselect.lua", {})

    @mcp.tool
    def select_by_color(
        session_id: str,
        color: str,
        tolerance: int = 0,
    ) -> dict:
        """按颜色选区（魔棒工具等效）。选择画布中所有匹配指定颜色的像素。

        Args:
            session_id: 会话 ID
            color: 目标颜色，格式 #RRGGBB
            tolerance: 颜色容差 0-255（0=精确匹配，越大越宽松），默认 0
        """
        color = validate_color(color)
        if tolerance < 0 or tolerance > 255:
            return {"success": False, "error": "tolerance must be 0-255"}
        return _run_sel_script(session_id, "select_by_color.lua", {
            "color": color, "tolerance": str(tolerance),
        })

    @mcp.tool
    def invert_selection(session_id: str) -> dict:
        """反选当前选区（Ctrl+Shift+I 等效）。

        Args:
            session_id: 会话 ID
        """
        return _run_sel_script(session_id, "invert_selection.lua", {})

    @mcp.tool
    def delete_selection(
        session_id: str,
        layer: int = 1,
        frame: int = 1,
    ) -> dict:
        """清除选区内容（设为透明）。相当于按 Delete 键。

        Args:
            session_id: 会话 ID
            layer: 目标图层（1-based，默认 1）
            frame: 目标帧（1-based，默认 1）
        """
        return run_script_with_file(
            runner, session_manager, session_id, "delete_selection.lua", {},
            layer=layer, frame=frame, error_label="Delete selection failed",
        )