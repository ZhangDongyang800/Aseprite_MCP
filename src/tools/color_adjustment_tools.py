"""颜色调整工具：亮度/对比度、色相/饱和度统一入口。

将 Aseprite 的 BrightnessContrast 和 HueSaturation 滤镜整合为一个工具，
避免分散的多个细粒度调整调用。
"""

from src.session import SessionManager
from src.tools.utils import run_script_with_file, validate_session_id


def register_color_adjustment_tools(mcp, session_manager: SessionManager, runner):
    """注册颜色调整工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool
    def adjust_colors(
        session_id: str,
        brightness: int = 0,
        contrast: int = 0,
        hue: int = 0,
        saturation: int = 0,
        lightness: int = 0,
    ) -> dict:
        """统一颜色调整：亮度/对比度/色相/饱和度/明度。未指定的参数保持不变。

        一次调用完成多项调整，替代多次单独调用。
        所有参数默认 0（不修改），只传需要调整的项。

        Args:
            session_id: 会话 ID
            brightness: 亮度 -100 到 100（默认 0）
            contrast: 对比度 -100 到 100（默认 0）
            hue: 色相 -180 到 180（默认 0）
            saturation: 饱和度 -100 到 100（默认 0）
            lightness: 明度 -100 到 100（默认 0）
        """
        # 验证参数范围
        for name, val, lo, hi in [
            ("brightness", brightness, -100, 100),
            ("contrast", contrast, -100, 100),
            ("saturation", saturation, -100, 100),
            ("lightness", lightness, -100, 100),
            ("hue", hue, -180, 180),
        ]:
            if val < lo or val > hi:
                return {"success": False, "error": f"{name} must be {lo} to {hi}"}

        return run_script_with_file(
            runner, session_manager, session_id, "adjust_colors.lua",
            {
                "brightness": str(brightness),
                "contrast": str(contrast),
                "hue": str(hue),
                "saturation": str(saturation),
                "lightness": str(lightness),
            },
            error_label="Color adjustment failed",
        )