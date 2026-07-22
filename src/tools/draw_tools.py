"""绘制原语工具：像素、线、矩形、椭圆、填充、清除。

每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行绘制操作。
"""

from pathlib import Path

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_color, validate_session_id


def register_draw_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册绘制原语工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_draw_script(
        session_id: str, script_name: str, params: dict
    ) -> dict:
        """执行绘制脚本的公共逻辑。

        Args:
            session_id: 会话 ID
            script_name: Lua 脚本名
            params: 脚本参数（不含 file）

        Returns:
            执行结果字典
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        # 添加 file 参数
        all_params = {"file": str(ase_path), **params}

        result = runner.run_script(script_name, all_params)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Draw operation failed"),
                "stderr": result.get("stderr", ""),
            }

        return {"success": True, "message": result.get("stdout", "").strip()}

    @mcp.tool
    def draw_pixel(session_id: str, x: int, y: int, color: str) -> dict:
        """在指定坐标画一个像素。

        Args:
            session_id: 会话 ID
            x: 像素 x 坐标（从 0 开始）
            y: 像素 y 坐标（从 0 开始）
            color: 颜色值，格式 #RRGGBB（如 #FF0000 表示红色）
        """
        color = validate_color(color)
        return _run_draw_script(session_id, "draw_pixel.lua", {
            "x": str(x), "y": str(y), "color": color,
        })

    @mcp.tool
    def draw_line(
        session_id: str,
        x1: int, y1: int,
        x2: int, y2: int,
        color: str,
    ) -> dict:
        """画一条直线。

        Args:
            session_id: 会话 ID
            x1: 起点 x 坐标
            y1: 起点 y 坐标
            x2: 终点 x 坐标
            y2: 终点 y 坐标
            color: 颜色值，格式 #RRGGBB
        """
        color = validate_color(color)
        return _run_draw_script(session_id, "draw_line.lua", {
            "x1": str(x1), "y1": str(y1),
            "x2": str(x2), "y2": str(y2),
            "color": color,
        })

    @mcp.tool
    def draw_rect(
        session_id: str,
        x: int, y: int,
        width: int, height: int,
        color: str,
        filled: bool = False,
    ) -> dict:
        """画一个矩形。

        Args:
            session_id: 会话 ID
            x: 矩形左上角 x 坐标
            y: 矩形左上角 y 坐标
            width: 矩形宽度
            height: 矩形高度
            color: 颜色值，格式 #RRGGBB
            filled: 是否填充，True 为实心，False 为空心（默认）
        """
        color = validate_color(color)
        return _run_draw_script(session_id, "draw_rect.lua", {
            "x": str(x), "y": str(y),
            "width": str(width), "height": str(height),
            "color": color,
            "filled": "true" if filled else "false",
        })

    @mcp.tool
    def draw_ellipse(
        session_id: str,
        cx: int, cy: int,
        rx: int, ry: int,
        color: str,
        filled: bool = False,
    ) -> dict:
        """画一个椭圆。

        Args:
            session_id: 会话 ID
            cx: 中心点 x 坐标
            cy: 中心点 y 坐标
            rx: x 方向半径
            ry: y 方向半径
            color: 颜色值，格式 #RRGGBB
            filled: 是否填充，True 为实心，False 为空心（默认）
        """
        color = validate_color(color)
        return _run_draw_script(session_id, "draw_ellipse.lua", {
            "cx": str(cx), "cy": str(cy),
            "rx": str(rx), "ry": str(ry),
            "color": color,
            "filled": "true" if filled else "false",
        })

    @mcp.tool
    def fill_region(session_id: str, x: int, y: int, color: str) -> dict:
        """油漆桶填充：填充与 (x,y) 相同颜色的连通区域。

        Args:
            session_id: 会话 ID
            x: 填充起始点 x 坐标
            y: 填充起始点 y 坐标
            color: 填充颜色，格式 #RRGGBB
        """
        color = validate_color(color)
        return _run_draw_script(session_id, "fill_region.lua", {
            "x": str(x), "y": str(y), "color": color,
        })

    @mcp.tool
    def clear_region(
        session_id: str,
        x: int, y: int,
        width: int, height: int,
    ) -> dict:
        """清除指定区域为透明。

        Args:
            session_id: 会话 ID
            x: 区域左上角 x 坐标
            y: 区域左上角 y 坐标
            width: 区域宽度
            height: 区域高度
        """
        return _run_draw_script(session_id, "clear_region.lua", {
            "x": str(x), "y": str(y),
            "width": str(width), "height": str(height),
        })

    @mcp.tool
    def clear_canvas(session_id: str) -> dict:
        """清空整个画布为透明。

        Args:
            session_id: 会话 ID
        """
        return _run_draw_script(session_id, "clear_canvas.lua", {})
