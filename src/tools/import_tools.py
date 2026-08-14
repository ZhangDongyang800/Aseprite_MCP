"""混合管线工具：AI 生成图清洗导入。

cleanup_import_image 把任意 AI 生成器的 PNG 输出清洗成干净的像素画
（恢复网格/去棋盘格/锁调色板/去噪），然后导入当前会话 sprite 指定图层。
清洗后的像素画可继续用动画一致性工作流做动画。
"""

from fastmcp.utilities.types import Image

from src.pixel_cleanup import PixelCleanupError, clean_image_file
from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import run_script_with_file, validate_session_id


def register_import_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册混合管线工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool
    def cleanup_import_image(
        session_id: str,
        image_path: str,
        max_colors: int = 24,
        palette: str = "",
        strip_background: bool = True,
        scale: int = 0,
        layer: int = 1,
        frame: int = 1,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> Image:
        """清洗 AI 生成图并导入为当前会话的图层，返回清洗结果预览图。

        混合管线（docs §12）：把任意扩散模型的输出变为干净、可编辑的像素画。
        管线步骤：检测整数放大倍率并降采样（去 mixels）→ 剥离棋盘格背景 →
        颜色收敛（锁定到 palette 或量化到 max_colors）→ 清除孤立噪点 → 导入。

        跨素材一致性：传入共享的 palette（如 "#1A1C2C,#5D275D,#B13E53"）可让
        所有素材共用同一套颜色词汇。返回的图片就是清洗结果，可视觉验证。

        Args:
            session_id: 会话 ID
            image_path: 输入 PNG 路径（AI 生成器的输出）
            max_colors: 量化目标颜色数（默认 24；palette 非空时忽略）
            palette: 锁定调色板，逗号分隔 #RRGGBB（如 "#1A1C2C,#B13E53"）
            strip_background: 是否剥离棋盘格背景（默认 True）
            scale: 强制缩放倍率（0=自动检测整数放大倍率，默认 0）
            layer: 导入目标图层（默认 1）
            frame: 导入目标帧（默认 1）
            offset_x/offset_y: 导入偏移（默认 0/0）
        """
        validate_session_id(session_id)
        if max_colors < 1 or max_colors > 256:
            raise ValueError("max_colors must be between 1 and 256")
        if layer < 1 or frame < 1:
            raise ValueError("layer and frame must be >= 1")

        work_dir = session_manager.get_work_dir(session_id)
        cleaned_path = work_dir / "cleaned.png"

        try:
            clean_image_file(
                src_path=image_path,
                out_path=str(cleaned_path),
                max_colors=max_colors,
                palette=palette,
                strip_background=strip_background,
                force_scale=scale,
            )
        except PixelCleanupError as e:
            raise RuntimeError(f"Cleanup failed: {e}") from e

        # 导入清洗结果为图层（复用 import_png.lua 的 stamp 模式）
        result = run_script_with_file(
            runner, session_manager, session_id, "import_png.lua",
            {
                "png_path": str(cleaned_path),
                "mode": "stamp",
                "layer": str(layer),
                "frame": str(frame),
                "offset_x": str(offset_x),
                "offset_y": str(offset_y),
            },
            error_label="Failed to import cleaned image",
        )
        if not result["success"]:
            raise RuntimeError(
                f"Failed to import cleaned image: {result.get('error', 'Unknown')}"
            )

        # 返回清洗结果预览图（即导入的内容）
        return Image(path=str(cleaned_path))
