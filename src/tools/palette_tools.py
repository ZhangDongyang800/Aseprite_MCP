"""调色板工具：设置颜色、获取调色板、调整大小、加载调色板。

每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行调色板操作。
"""

import json

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_color, validate_session_id


def register_palette_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册调色板工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_palette_script(
        session_id: str, script_name: str, params: dict
    ) -> dict:
        """执行调色板脚本的公共逻辑。

        Args:
            session_id: 会话 ID
            script_name: Lua 脚本名
            params: 脚本参数（不含 file）

        Returns:
            执行结果字典
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        # 添加 file 参数（会话 .ase 文件路径）
        all_params = {"file": str(ase_path), **params}

        result = runner.run_script(script_name, all_params)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Palette operation failed"),
                "stderr": result.get("stderr", ""),
            }

        return {"success": True, "message": result.get("stdout", "").strip()}

    @mcp.tool
    def set_palette_color(session_id: str, index: int, color: str) -> dict:
        """设置调色板指定索引的颜色。

        Args:
            session_id: 会话 ID
            index: 调色板索引（从 0 开始）
            color: 颜色值，格式 #RRGGBB（如 #FF0000 表示红色）
        """
        # 验证颜色格式
        color = validate_color(color)
        return _run_palette_script(session_id, "set_palette_color.lua", {
            "index": str(index), "color": color,
        })

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_palette(session_id: str) -> dict:
        """获取当前调色板的所有颜色。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        result = runner.run_script("get_palette.lua", {
            "file": str(ase_path),
        })

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to get palette"),
                "stderr": result.get("stderr", ""),
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

    @mcp.tool
    def resize_palette(session_id: str, size: int) -> dict:
        """调整调色板大小（颜色数量）。

        Args:
            session_id: 会话 ID
            size: 新的颜色数量
        """
        return _run_palette_script(session_id, "resize_palette.lua", {
            "size": str(size),
        })

    @mcp.tool
    def load_palette(session_id: str, palette_file: str) -> dict:
        """从文件加载调色板（.gpl/.pal/.png）。

        Args:
            session_id: 会话 ID
            palette_file: 调色板文件路径
        """
        return _run_palette_script(session_id, "load_palette.lua", {
            "palette_file": palette_file,
        })
