"""滤镜与特效工具：apply_blur 模糊滤镜。

ConvolutionMatrix 命令不支持自定义 kernel（仅 fromResource），
因此用纯 Lua 实现 box blur，确保 CLI/Live 双模式兼容。
"""

from src.session import SessionManager
from src.tools.utils import run_script_with_file, validate_session_id


def register_filter_tools(mcp, session_manager: SessionManager, runner):
    """注册滤镜与特效工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool
    def apply_blur(
        session_id: str,
        radius: int = 1,
        strength: int = 1,
        layer: int = 1,
        frame: int = 1,
    ) -> dict:
        """对指定图层/帧应用 box blur 模糊滤镜。

        Args:
            session_id: 会话 ID
            radius: 模糊半径 1-3（默认 1，越大越模糊）
            strength: 模糊强度 1-3（默认 1，越大越强）
            layer: 目标图层（1-based，默认 1）
            frame: 目标帧（1-based，默认 1）
        """
        if radius < 1 or radius > 3:
            return {"success": False, "error": "radius must be 1-3"}
        if strength < 1 or strength > 3:
            return {"success": False, "error": "strength must be 1-3"}

        return run_script_with_file(
            runner, session_manager, session_id, "apply_blur.lua",
            {"radius": str(radius), "strength": str(strength)},
            layer=layer, frame=frame, error_label="Blur operation failed",
        )