"""精灵管理工具：创建、打开、保存、关闭会话。

这些工具使用 @mcp.tool 装饰器注册到 FastMCP 服务器。
"""

from pathlib import Path

from src.session import SessionManager
from src.runner import AsepriteRunner


def register_sprite_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册精灵管理工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool
    def create_sprite(
        width: int,
        height: int,
        color_mode: str = "rgb",
    ) -> dict:
        """创建新的像素精灵画布。

        Args:
            width: 画布宽度（像素），如 16、32
            height: 画布高度（像素），如 16、32
            color_mode: 颜色模式，可选 "rgb"、"grayscale"、"indexed"，默认 rgb
        """
        # 创建会话
        session_id = session_manager.create_session(
            width=width, height=height, color_mode=color_mode
        )

        # 获取 .ase 文件路径
        ase_path = session_manager.get_ase_path(session_id)

        # 调用 Lua 脚本创建精灵
        result = runner.run_script("create_sprite.lua", {
            "width": str(width),
            "height": str(height),
            "color_mode": color_mode,
            "file": str(ase_path),
        })

        if not result["success"]:
            # 创建失败，清理会话
            session_manager.close_session(session_id)
            return {
                "success": False,
                "error": result.get("error", "Failed to create sprite"),
                "stderr": result.get("stderr", ""),
            }

        return {
            "success": True,
            "session_id": session_id,
            "file_path": str(ase_path),
            "width": width,
            "height": height,
            "color_mode": color_mode,
        }

    @mcp.tool
    def open_sprite(file_path: str) -> dict:
        """打开已有的精灵文件（.ase 或 .png）。

        Args:
            file_path: 要打开的文件路径
        """
        # 创建新会话（使用默认尺寸，后续从文件读取真实尺寸）
        session_id = session_manager.create_session(
            width=16, height=16, color_mode="rgb"
        )

        ase_path = session_manager.get_ase_path(session_id)

        # 调用 Lua 脚本打开并复制文件
        result = runner.run_script("open_sprite.lua", {
            "source": file_path,
            "dest": str(ase_path),
        })

        if not result["success"]:
            session_manager.close_session(session_id)
            return {
                "success": False,
                "error": result.get("error", "Failed to open sprite"),
                "stderr": result.get("stderr", ""),
            }

        return {
            "success": True,
            "session_id": session_id,
            "source": file_path,
            "file_path": str(ase_path),
        }

    @mcp.tool
    def save_sprite(session_id: str, output_path: str) -> dict:
        """将会话画布保存到指定路径。

        Args:
            session_id: 会话 ID（由 create_sprite 或 open_sprite 返回）
            output_path: 输出文件路径（支持 .ase、.png、.gif 格式）
        """
        from src.tools.utils import validate_session_id
        validate_session_id(session_id)

        # 确保输出路径为绝对路径，避免文件写到不可控位置
        output_path = str(Path(output_path).resolve())
        # 确保父目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        ase_path = session_manager.get_ase_path(session_id)

        result = runner.run_script("save_sprite.lua", {
            "file": str(ase_path),
            "output": output_path,
        })

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to save sprite"),
                "stderr": result.get("stderr", ""),
            }

        return {
            "success": True,
            "output_path": output_path,
        }

    @mcp.tool
    def close_session(session_id: str) -> dict:
        """关闭会话并清理资源。

        Args:
            session_id: 要关闭的会话 ID
        """
        from src.tools.utils import validate_session_id
        validate_session_id(session_id)

        session_manager.close_session(session_id)

        return {
            "success": True,
            "status": f"Session {session_id} closed",
        }
