"""动画标签工具：添加、移除、查询标签。

每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行标签操作。
"""

import json

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_session_id


def register_tag_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册动画标签工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_tag_script(
        session_id: str, script_name: str, params: dict
    ) -> dict:
        """执行标签脚本的公共逻辑。

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
                "error": result.get("error", "Tag operation failed"),
                "stderr": result.get("stderr", ""),
            }

        return {"success": True, "message": result.get("stdout", "").strip()}

    @mcp.tool
    def add_tag(
        session_id: str,
        name: str,
        from_frame: int,
        to_frame: int,
        ani_dir: str = "forward",
        repeats: int = 0,
    ) -> dict:
        """添加动画标签。

        Args:
            session_id: 会话 ID
            name: 标签名称（如 "Walk"）
            from_frame: 起始帧（1-indexed）
            to_frame: 结束帧（1-indexed）
            ani_dir: 动画方向，可选 "forward"/"reverse"/"ping_pong"/"ping_pong_reverse"，默认 "forward"
            repeats: 重复次数，默认 0
        """
        return _run_tag_script(session_id, "add_tag.lua", {
            "name": name,
            "from_frame": str(from_frame),
            "to_frame": str(to_frame),
            "ani_dir": ani_dir,
            "repeats": str(repeats),
        })

    @mcp.tool
    def remove_tag(session_id: str, name: str) -> dict:
        """按名称移除动画标签。

        Args:
            session_id: 会话 ID
            name: 要移除的标签名称
        """
        return _run_tag_script(session_id, "remove_tag.lua", {
            "name": name,
        })

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_tags(session_id: str) -> dict:
        """获取所有动画标签。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        result = runner.run_script("get_tags.lua", {
            "file": str(ase_path),
        })

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to get tags"),
                "stderr": result.get("stderr", ""),
            }

        # 解析 Lua 脚本输出的 JSON 数组
        try:
            tags = json.loads(result["stdout"].strip())
            return {"success": True, "tags": tags}
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Failed to parse response: {result['stdout']}",
            }
