"""图像变换工具：翻转、缩放、反色、替换颜色、旋转、裁剪。

每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行变换操作。
"""

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_color, validate_session_id


def register_transform_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册图像变换工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_transform_script(
        session_id: str, script_name: str, params: dict
    ) -> dict:
        """执行变换脚本的公共逻辑。

        Args:
            session_id: 会话 ID
            script_name: Lua 脚本名
            params: 脚本参数（不含 file）

        Returns:
            执行结果字典
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        # 添加 file 参数（Lua 脚本通过 app.params["file"] 读取）
        all_params = {"file": str(ase_path), **params}

        result = runner.run_script(script_name, all_params)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Transform operation failed"),
                "stderr": result.get("stderr", ""),
            }

        return {"success": True, "message": result.get("stdout", "").strip()}

    @mcp.tool
    def flip_canvas(session_id: str, direction: str = "horizontal") -> dict:
        """翻转画布（水平或垂直镜像）。

        Args:
            session_id: 会话 ID
            direction: 翻转方向，"horizontal"（水平翻转）或 "vertical"（垂直翻转），默认 horizontal
        """
        # 验证翻转方向：仅允许 horizontal 或 vertical
        if direction not in ("horizontal", "vertical"):
            return {
                "success": False,
                "error": f"Invalid direction: {direction!r}. Must be 'horizontal' or 'vertical'",
            }
        return _run_transform_script(session_id, "flip_canvas.lua", {
            "direction": direction,
        })

    @mcp.tool
    def resize_sprite(session_id: str, width: int, height: int) -> dict:
        """调整精灵尺寸（缩放整个画布）。

        Args:
            session_id: 会话 ID
            width: 新宽度（像素）
            height: 新高度（像素）
        """
        # 验证尺寸必须为正整数
        if width <= 0 or height <= 0:
            return {
                "success": False,
                "error": f"Invalid dimensions: width={width}, height={height}. Must be positive integers",
            }
        return _run_transform_script(session_id, "resize_sprite.lua", {
            "width": str(width), "height": str(height),
        })

    @mcp.tool
    def invert_color(session_id: str) -> dict:
        """反转画布所有颜色（反色效果）。

        Args:
            session_id: 会话 ID
        """
        return _run_transform_script(session_id, "invert_color.lua", {})

    @mcp.tool
    def replace_color(
        session_id: str, from_color: str, to_color: str
    ) -> dict:
        """将画布中的一种颜色替换为另一种颜色。

        Args:
            session_id: 会话 ID
            from_color: 要被替换的颜色，格式 #RRGGBB（如 #FF0000）
            to_color: 替换后的颜色，格式 #RRGGBB（如 #00FF00）
        """
        # 验证颜色格式（utils.validate_color 会抛出 ValueError）
        from_color = validate_color(from_color)
        to_color = validate_color(to_color)
        return _run_transform_script(session_id, "replace_color.lua", {
            "from_color": from_color, "to_color": to_color,
        })

    @mcp.tool
    def rotate_canvas(session_id: str, angle: int) -> dict:
        """旋转画布。

        Args:
            session_id: 会话 ID
            angle: 旋转角度，必须是 90、180 或 270 度
        """
        # 验证角度值：仅允许 90、180、270
        if angle not in (90, 180, 270):
            return {
                "success": False,
                "error": f"Invalid angle: {angle}. Must be 90, 180, or 270",
            }
        return _run_transform_script(session_id, "rotate_canvas.lua", {
            "angle": str(angle),
        })

    @mcp.tool
    def crop_sprite(
        session_id: str, x: int, y: int, width: int, height: int
    ) -> dict:
        """裁剪精灵到指定矩形区域。

        Args:
            session_id: 会话 ID
            x: 裁剪区域左上角 x 坐标
            y: 裁剪区域左上角 y 坐标
            width: 裁剪区域宽度
            height: 裁剪区域高度
        """
        # 验证裁剪区域尺寸必须为正整数
        if width <= 0 or height <= 0:
            return {
                "success": False,
                "error": f"Invalid crop dimensions: width={width}, height={height}. Must be positive integers",
            }
        return _run_transform_script(session_id, "crop_sprite.lua", {
            "x": str(x), "y": str(y),
            "width": str(width), "height": str(height),
        })
