"""检查与导出工具：预览画布、获取信息、查询像素颜色。

get_canvas_preview 是核心工具：导出 PNG 并返回 Image 对象，
让多模态 AI 能够"看到"画布内容并迭代修正。
"""

import json

from fastmcp.utilities.types import Image

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_session_id


def register_inspect_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册检查与导出工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_canvas_preview(session_id: str, scale: int = 1) -> Image:
        """导出当前画布为 PNG 并返回图片，供 AI 视觉分析。

        这是迭代绘制循环的核心工具：绘制后调用此工具查看效果，
        分析图片后决定是否需要修正。

        Args:
            session_id: 会话 ID（由 create_sprite 返回）
            scale: 放大倍数（1=原始尺寸，2=2倍，便于 AI 看清单像素）
        """
        validate_session_id(session_id)

        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        png_path = work_dir / "preview.png"

        # 调用 Lua 脚本导出 PNG
        result = runner.run_script("export_png.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "scale": str(scale),
        })

        if not result["success"]:
            raise RuntimeError(
                f"Failed to export preview: {result.get('error', 'Unknown error')}"
            )

        # 返回 Image 对象（FastMCP 自动 base64 编码）
        return Image(path=str(png_path))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_canvas_info(session_id: str) -> dict:
        """获取画布元数据（不返回图片）。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)
        return session_manager.get_canvas_info(session_id)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_pixel_color(session_id: str, x: int, y: int) -> dict:
        """查询指定像素的颜色。

        Args:
            session_id: 会话 ID
            x: 像素 x 坐标
            y: 像素 y 坐标
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        result = runner.run_script("get_pixel_color.lua", {
            "file": str(ase_path),
            "x": str(x),
            "y": str(y),
        })

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to get pixel color"),
            }

        # 解析 Lua 脚本输出的 JSON
        try:
            data = json.loads(result["stdout"].strip())
            if "error" in data:
                return {"success": False, "error": data["error"]}
            return {"success": True, **data}
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Failed to parse response: {result['stdout']}",
            }
