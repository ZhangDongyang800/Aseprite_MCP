"""高级绘制工具：网格绘制、自动描边、镜像复制。

这些工具封装了复杂的坐标计算，减少 LLM 的规划负担：
- draw_from_grid: 用文本网格一次性绘制整幅像素图（最高效）
- add_outline: 自动为已有像素添加轮廓描边
- mirror_half: 镜像复制半幅画布到另一半（用于对称角色）
"""

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_color, validate_session_id


def register_advanced_draw_tools(
    mcp, session_manager: SessionManager, runner: AsepriteRunner
):
    """注册高级绘制工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_advanced_script(
        session_id: str, script_name: str, params: dict,
        layer: int = 1, frame: int = 1,
    ) -> dict:
        """执行高级绘制脚本的公共逻辑。

        Args:
            session_id: 会话 ID
            script_name: Lua 脚本名
            params: 脚本参数（不含 file、layer、frame）
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）

        Returns:
            执行结果字典
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        # 添加 file、layer、frame 参数
        all_params = {
            "file": str(ase_path),
            "layer": str(layer),
            "frame": str(frame),
            **params,
        }

        result = runner.run_script(script_name, all_params)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Advanced draw operation failed"),
                "stderr": result.get("stderr", ""),
            }

        return {"success": True, "message": result.get("stdout", "").strip()}

    @mcp.tool
    def draw_from_grid(
        session_id: str,
        grid: str,
        colormap: str,
        offset_x: int = 0,
        offset_y: int = 0,
        layer: int = 1,
        frame: int = 1,
    ) -> dict:
        """从文本网格一次性绘制整幅像素图（推荐的高效绘制方式）。

        用一个字符串表示整个像素布局，每个字符映射一种颜色，
        一次性绘制完成，无需逐像素调用 draw_pixel。

        Args:
            session_id: 会话 ID
            grid: 像素网格字符串，用 / 分隔行，每行每个字符代表一个像素。
                  例如 3x3 红底白心: "RRR/RWR/RRR"
            colormap: 颜色映射表，用 , 分隔的 字符=颜色 对。
                      颜色用 #RRGGBB 格式，transparent 表示透明。
                      例如: "R=#FF0000,W=#FFFFFF,.=transparent"
            offset_x: 绘制起始 x 坐标偏移（默认0）
            offset_y: 绘制起始 y 坐标偏移（默认0）
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）

        示例:
            grid = "....BBBB...." / "..BBYYYYBB.." / "..BYYYYYYB.." / "...BBBBBB..."
            colormap = "B=#8B4513,Y=#FFD700,.=transparent"
        """
        if not grid or not colormap:
            return {
                "success": False,
                "error": "grid and colormap are required",
            }
        return _run_advanced_script(
            session_id, "draw_from_grid.lua",
            {
                "grid": grid,
                "colormap": colormap,
                "offset_x": str(offset_x),
                "offset_y": str(offset_y),
            },
            layer, frame,
        )

    @mcp.tool
    def add_outline(
        session_id: str,
        color: str = "#000000",
        thickness: int = 1,
        layer: int = 1,
        frame: int = 1,
    ) -> dict:
        """自动为画布上已有的像素添加轮廓描边。

        找到所有非透明像素边缘的透明位置，用指定颜色填充，
        形成描边效果。无需手动指定轮廓坐标。

        Args:
            session_id: 会话 ID
            color: 轮廓颜色，格式 #RRGGBB（默认 #000000 黑色）
            thickness: 轮廓粗细（1=1像素描边，2=2像素描边，默认1）
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        color = validate_color(color)
        if thickness < 1 or thickness > 5:
            return {
                "success": False,
                "error": f"Invalid thickness: {thickness}. Must be 1-5",
            }
        return _run_advanced_script(
            session_id, "add_outline.lua",
            {"color": color, "thickness": str(thickness)},
            layer, frame,
        )

    @mcp.tool
    def mirror_half(
        session_id: str,
        axis: str = "x",
        position: int = 0,
        direction: str = "left_to_right",
        layer: int = 1,
        frame: int = 1,
    ) -> dict:
        """镜像复制半幅画布到另一半（用于绘制对称角色）。

        只需绘制左半部分（或上半部分），此工具自动镜像到右半部分（或下半部分），
        大幅减少绘制工作量。常用于角色正面像、图标等对称图形。

        Args:
            session_id: 会话 ID
            axis: 镜像轴，"x"=水平镜像（左右复制），"y"=垂直镜像（上下复制），默认 "x"
            position: 镜像轴位置坐标（水平镜像时是 x 坐标，垂直镜像时是 y 坐标）。
                      对于 16x16 画布水平镜像，position=8 表示从第8列镜像
            direction: 复制方向。
                       "left_to_right"=从左复制到右，
                       "right_to_left"=从右复制到左，
                       "top_to_bottom"=从上复制到下，
                       "bottom_to_top"=从下复制到上。
                       默认 "left_to_right"
            layer: 目标图层索引（1-based，默认1）
            frame: 目标帧索引（1-based，默认1）
        """
        if axis not in ("x", "y"):
            return {
                "success": False,
                "error": f"Invalid axis: {axis!r}. Must be 'x' or 'y'",
            }
        valid_dirs = (
            "left_to_right", "right_to_left",
            "top_to_bottom", "bottom_to_top",
        )
        if direction not in valid_dirs:
            return {
                "success": False,
                "error": f"Invalid direction: {direction!r}. Must be one of {valid_dirs}",
            }
        return _run_advanced_script(
            session_id, "mirror_half.lua",
            {
                "axis": axis,
                "position": str(position),
                "direction": direction,
            },
            layer, frame,
        )
