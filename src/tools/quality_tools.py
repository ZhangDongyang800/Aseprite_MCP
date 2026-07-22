"""质量检查工具：剪影测试与规范检查（docs §3.6/§5/§11）。

把 docs 的自检规范变成 AI 可调用的工具，交付前自动发现常见问题。
"""

import json
from pathlib import Path

from fastmcp.utilities.types import Image

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_session_id


def register_quality_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册质量检查工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def export_silhouette(session_id: str, scale: int = 4) -> Image:
        """导出纯黑剪影 PNG（docs §3.6 剪影测试）。

        所有非透明像素变黑。剪影若不清晰则造型需调整。
        这是专业像素美术的招牌自检：纯黑也能辨识出是什么说明造型扎实。

        Args:
            session_id: 会话 ID
            scale: 放大倍数（默认 4）
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        # 剪影 PNG 输出路径（每次覆盖，无需唯一命名）
        png_path = work_dir / "silhouette.png"

        # 调用 export_silhouette.lua 把非透明像素染黑后放大导出
        result = runner.run_script("export_silhouette.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "scale": str(scale),
        })
        if not result["success"]:
            raise RuntimeError(
                f"Failed to export silhouette: {result.get('error', 'Unknown')}"
            )
        return Image(path=str(png_path))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def check_canvas_standards(session_id: str) -> dict:
        """检查画布是否符合 docs 规范，返回结构化报告。

        检查项（每项 pass/detail/suggestion）：
        - size: 尺寸是否为 8 的倍数（§2.1）
        - color_count: 颜色数是否在 4-32（§4.1）
        - timing: 多帧时是否统一帧率（§7.2，统一则警告）
        - pixel_art: 半透明像素/孤立像素（§5），jaggies 形状需视觉复查

        报告全 pass 可跳过 preview 直接导出（减少调用）。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        # 调用 check_standards.lua，脚本会打印 JSON 报告到 stdout
        result = runner.run_script("check_standards.lua", {
            "file": str(ase_path),
        })
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Standards check failed"),
            }
        try:
            # Lua 脚本以 JSON 字符串形式输出，需要解析
            data = json.loads(result["stdout"].strip())
            if "error" in data:
                # 脚本内部报错（如文件无法打开）
                return {"success": False, "error": data["error"]}
            return data
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Failed to parse response: {result['stdout']}",
            }
