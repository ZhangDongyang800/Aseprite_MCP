"""动画工具：帧管理与导出。

提供帧的增删改查、帧持续时间设置、GIF 导出和精灵表导出功能。
每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行操作。
"""

import json

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_session_id


def register_animation_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册动画工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_anim_script(
        session_id: str, script_name: str, params: dict
    ) -> dict:
        """执行动画脚本的公共逻辑。

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
                "error": result.get("error", "Animation operation failed"),
                "stderr": result.get("stderr", ""),
            }

        return {"success": True, "message": result.get("stdout", "").strip()}

    @mcp.tool
    def add_frame(session_id: str, content: str = "copy") -> dict:
        """添加新帧（复制最后一帧或创建空白帧）。

        Args:
            session_id: 会话 ID
            content: 帧内容类型，"copy" 复制最后一帧（默认），"empty" 创建空白帧
        """
        return _run_anim_script(session_id, "add_frame.lua", {
            "content": content,
        })

    @mcp.tool
    def remove_frame(session_id: str, frame: int) -> dict:
        """删除指定帧。

        Args:
            session_id: 会话 ID
            frame: 帧号（1-indexed）
        """
        return _run_anim_script(session_id, "remove_frame.lua", {
            "frame": str(frame),
        })

    @mcp.tool
    def set_frame_duration(session_id: str, frame: int, duration: float) -> dict:
        """设置帧持续时间。

        Args:
            session_id: 会话 ID
            frame: 帧号（1-indexed）
            duration: 持续时间（秒）
        """
        return _run_anim_script(session_id, "set_frame_duration.lua", {
            "frame": str(frame),
            "duration": str(duration),
        })

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_frame_info(session_id: str) -> dict:
        """获取所有帧信息（帧数、每帧持续时间）。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        result = runner.run_script("get_frame_info.lua", {
            "file": str(ase_path),
        })

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to get frame info"),
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
    def export_gif(session_id: str, output_path: str, scale: int = 1) -> dict:
        """导出为 GIF 动画。

        Args:
            session_id: 会话 ID
            output_path: GIF 输出路径
            scale: 缩放倍数（默认 1）
        """
        return _run_anim_script(session_id, "export_gif.lua", {
            "output": output_path,
            "scale": str(scale),
        })

    @mcp.tool
    def export_sprite_sheet(
        session_id: str,
        output_path: str,
        columns: int = 0,
        data_output: str = "",
        sheet_type: str = "horizontal",
    ) -> dict:
        """导出精灵表（Sprite Sheet）。

        Args:
            session_id: 会话 ID
            output_path: PNG 输出路径
            columns: 列数（0=自动，默认 0）
            data_output: JSON 数据输出路径（可选，空字符串表示不导出数据）
            sheet_type: 排列类型，可选 "horizontal"/"vertical"/"rows"/"columns"/"packed"（默认 "horizontal"）
        """
        params = {
            "output": output_path,
            "columns": str(columns),
            "type": sheet_type,
        }
        # 仅在提供数据输出路径时添加 data_output 参数
        if data_output:
            params["data_output"] = data_output
        return _run_anim_script(session_id, "export_sprite_sheet.lua", params)
