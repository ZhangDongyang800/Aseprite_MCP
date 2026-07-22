"""MCP Resources：只读数据源。

提供会话列表、调色板、画布信息等只读数据。
"""

import json

from src.session import SessionManager


# Aseprite 默认调色板（经典 16 色像素艺术调色板）
_DEFAULT_PALETTE = [
    "#000000", "#1D2B53", "#7E2553", "#008751",
    "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
    "#FF004D", "#FFA300", "#FFEC27", "#00E436",
    "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA",
]


def register_resources(mcp, session_manager: SessionManager):
    """注册 MCP Resources。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
    """

    @mcp.resource("aseprite://sessions")
    def list_sessions() -> str:
        """列出当前所有活跃的绘制会话。"""
        return json.dumps(session_manager.list_sessions())

    @mcp.resource("aseprite://palette/default")
    def get_default_palette() -> str:
        """返回默认像素艺术调色板（16 色）。"""
        return json.dumps({"colors": _DEFAULT_PALETTE})

    @mcp.resource("aseprite://canvas/{session_id}/info")
    def get_canvas_info_resource(session_id: str) -> str:
        """获取指定会话的画布元数据。"""
        info = session_manager.get_canvas_info(session_id)
        return json.dumps(info)
