"""精灵管理工具：创建、打开、保存、关闭会话。

这些工具使用 @mcp.tool 装饰器注册到 FastMCP 服务器。
"""

import json
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

    @mcp.tool
    def import_png(
        png_path: str,
        mode: str = "new",
        session_id: str = "",
        layer: int = 1,
        frame: int = 1,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> dict:
        """★推荐★ 从 PNG 文件导入图像，画任意图形的最省 token 方式。

        比 draw_from_grid 的字符串网格更直观、更省 token：AI 只需写几行
        Python/PIL 代码生成 PNG，再调用本工具一次导入，无需逐像素描述。

        两种模式：
        - mode="new"（默认）：从 PNG 创建新会话，自动读取真实尺寸。
          适合"从零生成一张图再导入"。
        - mode="stamp"：把 PNG 贴到已有会话的指定图层/帧/偏移位置。
          适合叠加细节、贴图章、组合多张子图。

        推荐工作流（画任意图）：
        1. AI 写 Python 代码用 PIL 生成 temp.png
        2. import_png(mode="new", png_path="temp.png") 得到会话
        3. 用 draw_pixel/draw_rect 等工具精修

        Args:
            png_path: PNG 文件路径（必填）
            mode: "new" 新建会话 / "stamp" 贴到已有会话（默认 "new"）
            session_id: 会话 ID（stamp 模式必填，new 模式忽略）
            layer: 目标图层索引（stamp 模式，1-based，默认1）
            frame: 目标帧索引（stamp 模式，1-based，默认1）
            offset_x: stamp 模式 x 偏移（默认0）
            offset_y: stamp 模式 y 偏移（默认0）
        """
        from src.tools.utils import validate_session_id

        # 解析为绝对路径，避免相对路径导致找不到文件
        png_path = str(Path(png_path).resolve())
        if not Path(png_path).exists():
            return {"success": False, "error": f"png not found: {png_path}"}

        if mode == "new":
            # new 模式：创建占位会话，尺寸后续用 PNG 真实值刷新
            new_session_id = session_manager.create_session(
                width=16, height=16, color_mode="rgb"
            )
            ase_path = session_manager.get_ase_path(new_session_id)

            result = runner.run_script("import_png.lua", {
                "png_path": png_path,
                "mode": "new",
                "dest": str(ase_path),
            })

            if not result["success"]:
                # 失败时清理会话，避免泄漏
                session_manager.close_session(new_session_id)
                return {
                    "success": False,
                    "error": result.get("error", "Failed to import png"),
                    "stderr": result.get("stderr", ""),
                }

            # 解析 Lua 输出的尺寸 JSON
            try:
                data = json.loads(result["stdout"].strip())
                if "error" in data:
                    session_manager.close_session(new_session_id)
                    return {"success": False, "error": data["error"]}
                width = data["width"]
                height = data["height"]
            except (json.JSONDecodeError, KeyError):
                session_manager.close_session(new_session_id)
                return {
                    "success": False,
                    "error": f"Failed to parse size: {result.get('stdout', '')}",
                }

            # 用真实尺寸刷新会话缓存
            session_manager.update_canvas_info(new_session_id, width, height)

            return {
                "success": True,
                "session_id": new_session_id,
                "file_path": str(ase_path),
                "width": width,
                "height": height,
                "source": png_path,
            }

        elif mode == "stamp":
            if not session_id:
                return {
                    "success": False,
                    "error": "session_id is required for stamp mode",
                }
            validate_session_id(session_id)
            ase_path = session_manager.get_ase_path(session_id)

            result = runner.run_script("import_png.lua", {
                "png_path": png_path,
                "mode": "stamp",
                "file": str(ase_path),
                "layer": str(layer),
                "frame": str(frame),
                "offset_x": str(offset_x),
                "offset_y": str(offset_y),
            })

            if not result["success"]:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to stamp png"),
                    "stderr": result.get("stderr", ""),
                }

            # 检查 Lua 是否输出错误 JSON
            try:
                data = json.loads(result["stdout"].strip())
                if "error" in data:
                    return {"success": False, "error": data["error"]}
            except json.JSONDecodeError:
                pass

            return {
                "success": True,
                "session_id": session_id,
                "stamped_at": {
                    "layer": layer, "frame": frame,
                    "offset_x": offset_x, "offset_y": offset_y,
                },
                "source": png_path,
            }

        else:
            return {
                "success": False,
                "error": f"invalid mode: {mode}. Must be 'new' or 'stamp'",
            }
