"""Tileset 工具：瓦片画布创建与拼接预览（docs §8）。

补齐当前完全缺失的 Tileset 制作能力，专注瓦片画布创建与接缝自检。
"""

from fastmcp.utilities.types import Image

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import run_script_with_file, validate_session_id


def register_tileset_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册 Tileset 工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    # 允许的瓦片尺寸（docs §8.1）
    _ALLOWED_TILE_SIZES = {16, 32, 64}

    def _run_tileset_script(session_id: str, script_name: str, params: dict) -> dict:
        """执行 Tileset 脚本（委托 utils.run_script_with_file）。"""
        return run_script_with_file(
            runner, session_manager, session_id, script_name, params,
            error_label="Tileset operation failed",
        )

    @mcp.tool
    def create_tileset_canvas(
        session_id: str, tile_size: int, cols: int, rows: int
    ) -> dict:
        """创建瓦片画布并设置网格为瓦片尺寸（docs §8.5）。

        画布尺寸 = tile_size × cols × tile_size × rows。
        网格=瓦片尺寸让 AI 清晰看到瓦片边界，避免越界污染相邻瓦片。

        Args:
            session_id: 会话 ID
            tile_size: 单块瓦片尺寸（仅支持 16/32/64）
            cols: 横向瓦片数
            rows: 纵向瓦片数
        """
        if tile_size not in _ALLOWED_TILE_SIZES:
            return {
                "success": False,
                "error": f"Invalid tile_size: {tile_size}. Must be one of {sorted(_ALLOWED_TILE_SIZES)}",
            }
        if cols < 1 or rows < 1:
            return {"success": False, "error": "cols and rows must be >= 1"}
        return _run_tileset_script(session_id, "create_tileset.lua", {
            "tile_size": str(tile_size), "cols": str(cols), "rows": str(rows),
        })

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def export_tiled_preview(session_id: str, repeat: int = 2, scale: int = 4) -> Image:
        """导出平铺拼接预览 PNG，检查瓦片接缝（docs §8.4/§11.5）。

        把当前画布当单个瓦片，导出 repeat×repeat 拼接图。
        Tileset 最大坑是接缝：单看正常，拼接才暴露。本工具是 AI 的"拼接预览眼"。

        Args:
            session_id: 会话 ID
            repeat: 每方向重复次数（默认 2，即 2x2）
            scale: 放大倍数（默认 4）
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        png_path = work_dir / f"tiled_{repeat}x{repeat}.png"

        result = runner.run_script("export_tiled.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "repeat": str(repeat),
            "scale": str(scale),
        })
        if not result["success"]:
            raise RuntimeError(
                f"Failed to export tiled preview: {result.get('error', 'Unknown')}"
            )
        return Image(path=str(png_path))
