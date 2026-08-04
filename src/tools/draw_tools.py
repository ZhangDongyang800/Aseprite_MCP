"""绘制原语工具：像素、线、矩形、椭圆、填充、清除。

每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行绘制操作。
支持指定图层和帧，默认在第1图层第1帧绘制。
"""

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import (
    run_script_with_file, validate_color, validate_session_id,
)


def register_draw_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册绘制原语工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool
    def draw_pixel(
        session_id: str, x: int, y: int, color: str,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """在指定坐标画一个像素。适合最终微调（1-5个像素修正）。

        大量像素请用 draw_from_grid（一次调用绘制整幅图），多帧动画请用 draw_animation_frames。

        Args:
            session_id: 会话 ID
            x: 像素 x 坐标（从 0 开始）
            y: 像素 y 坐标（从 0 开始）
            color: 颜色值，格式 #RRGGBB（如 #FF0000 表示红色）
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        color = validate_color(color)
        return run_script_with_file(runner, session_manager, session_id, "draw_pixel.lua", {
            "x": str(x), "y": str(y), "color": color,
        }, layer, frame)

    @mcp.tool
    def draw_line(
        session_id: str,
        x1: int, y1: int,
        x2: int, y2: int,
        color: str,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """画一条直线。适合单条结构线（1-3条）。

        Args:
            session_id: 会话 ID
            x1: 起点 x 坐标
            y1: 起点 y 坐标
            x2: 终点 x 坐标
            y2: 终点 y 坐标
            color: 颜色值，格式 #RRGGBB
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        color = validate_color(color)
        return run_script_with_file(runner, session_manager, session_id, "draw_line.lua", {
            "x1": str(x1), "y1": str(y1),
            "x2": str(x2), "y2": str(y2),
            "color": color,
        }, layer, frame)

    @mcp.tool
    def draw_rect(
        session_id: str,
        x: int, y: int,
        width: int, height: int,
        color: str,
        filled: bool = False,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """画一个矩形（空心或实心）。适合独立绘制的少量矩形（1-3个）。

        Args:
            session_id: 会话 ID
            x: 矩形左上角 x 坐标
            y: 矩形左上角 y 坐标
            width: 矩形宽度
            height: 矩形高度
            color: 颜色值，格式 #RRGGBB
            filled: 是否填充，True 为实心，False 为空心（默认）
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        color = validate_color(color)
        return run_script_with_file(runner, session_manager, session_id, "draw_rect.lua", {
            "x": str(x), "y": str(y),
            "width": str(width), "height": str(height),
            "color": color,
            "filled": "true" if filled else "false",
        }, layer, frame)

    @mcp.tool
    def draw_ellipse(
        session_id: str,
        cx: int, cy: int,
        rx: int, ry: int,
        color: str,
        filled: bool = False,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """画一个椭圆（空心或实心）。适合单独绘制的少量椭圆。

        Args:
            session_id: 会话 ID
            cx: 中心点 x 坐标
            cy: 中心点 y 坐标
            rx: x 方向半径
            ry: y 方向半径
            color: 颜色值，格式 #RRGGBB
            filled: 是否填充，True 为实心，False 为空心（默认）
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        color = validate_color(color)
        return run_script_with_file(runner, session_manager, session_id, "draw_ellipse.lua", {
            "cx": str(cx), "cy": str(cy),
            "rx": str(rx), "ry": str(ry),
            "color": color,
            "filled": "true" if filled else "false",
        }, layer, frame)

    @mcp.tool
    def fill_region(
        session_id: str, x: int, y: int, color: str,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """油漆桶填充：填充与 (x,y) 相同颜色的连通区域。

        Args:
            session_id: 会话 ID
            x: 填充起始点 x 坐标
            y: 填充起始点 y 坐标
            color: 填充颜色，格式 #RRGGBB
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        color = validate_color(color)
        return run_script_with_file(runner, session_manager, session_id, "fill_region.lua", {
            "x": str(x), "y": str(y), "color": color,
        }, layer, frame)

    @mcp.tool
    def clear_region(
        session_id: str,
        x: int, y: int,
        width: int, height: int,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """清除指定区域为透明。

        Args:
            session_id: 会话 ID
            x: 区域左上角 x 坐标
            y: 区域左上角 y 坐标
            width: 区域宽度
            height: 区域高度
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        return run_script_with_file(runner, session_manager, session_id, "clear_region.lua", {
            "x": str(x), "y": str(y),
            "width": str(width), "height": str(height),
        }, layer, frame)

    @mcp.tool
    def clear_canvas(
        session_id: str,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """清空整个画布为透明。

        Args:
            session_id: 会话 ID
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        return run_script_with_file(runner, session_manager, session_id, "clear_canvas.lua", {}, layer, frame)
