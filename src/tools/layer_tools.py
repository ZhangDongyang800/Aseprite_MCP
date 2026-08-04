"""图层管理工具：添加、删除、设置属性、查询信息、移动 cel、合并、复制。

每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行图层操作。
"""

from typing import Optional

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import (
    backup_ase_file, parse_json_output, run_script_with_file,
    validate_session_id,
)


def register_layer_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册图层管理工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    def _run_layer_script(
        session_id: str, script_name: str, params: dict
    ) -> dict:
        """执行图层脚本（委托 utils.run_script_with_file）。"""
        return run_script_with_file(
            runner, session_manager, session_id, script_name, params,
            error_label="Layer operation failed",
        )

    @mcp.tool
    def add_layer(session_id: str, name: str = "Layer") -> dict:
        """创建新图层。

        Args:
            session_id: 会话 ID
            name: 图层名称（默认 "Layer"）
        """
        return _run_layer_script(session_id, "add_layer.lua", {
            "name": name,
        })

    @mcp.tool
    def remove_layer(session_id: str, layer: str) -> dict:
        """删除指定图层。

        Args:
            session_id: 会话 ID
            layer: 图层名称或 1-based 索引
        """
        return _run_layer_script(session_id, "remove_layer.lua", {
            "layer": str(layer),
        })

    @mcp.tool
    def set_layer_properties(
        session_id: str,
        layer: str,
        name: str = "",
        visible: Optional[bool] = None,
        opacity: Optional[int] = None,
        blend_mode: str = "",
    ) -> dict:
        """设置图层属性（仅修改提供的参数，未提供的保持不变）。

        Args:
            session_id: 会话 ID
            layer: 图层名称或 1-based 索引
            name: 新图层名称（留空则不修改）
            visible: 是否可见（True/False，None 则不修改）
            opacity: 不透明度 0-255（None 则不修改）
            blend_mode: 混合模式，如 "normal"、"multiply"、"screen" 等（留空则不修改）
        """
        # 构建参数，仅包含有值的参数（跳过空字符串和 None）
        params = {"layer": str(layer)}
        if name:
            params["name"] = name
        if visible is not None:
            params["visible"] = "true" if visible else "false"
        if opacity is not None:
            params["opacity"] = str(opacity)
        if blend_mode:
            params["blend_mode"] = blend_mode

        return _run_layer_script(session_id, "set_layer_properties.lua", params)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_layer_info(session_id: str) -> dict:
        """获取所有图层的详细信息。

        返回每个图层的名称、索引、可见性、不透明度、混合模式、
        是否为背景图层、是否为图层组。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        result = runner.run_script("get_layer_info.lua", {"file": str(ase_path)})
        layers, error = parse_json_output(result, "Failed to get layer info")
        if error:
            return error
        return {"success": True, "layers": layers}

    @mcp.tool
    def move_cel(
        session_id: str,
        source_layer: str,
        source_frame: int,
        dest_layer: str,
        dest_frame: int,
    ) -> dict:
        """将 cel 从源图层/帧移动到目标图层/帧。

        克隆源 cel 的图像，在目标位置创建新 cel，然后删除原始 cel。

        Args:
            session_id: 会话 ID
            source_layer: 源图层名称或 1-based 索引
            source_frame: 源帧号（1-based）
            dest_layer: 目标图层名称或 1-based 索引
            dest_frame: 目标帧号（1-based）
        """
        return _run_layer_script(session_id, "move_cel.lua", {
            "source_layer": str(source_layer),
            "source_frame": str(source_frame),
            "dest_layer": str(dest_layer),
            "dest_frame": str(dest_frame),
        })

    @mcp.tool
    def merge_down(session_id: str, layer: str = "") -> dict:
        """合并指定图层到下层（Ctrl+E 等效）。不指定则合并当前活跃图层。

        Args:
            session_id: 会话 ID
            layer: 图层名称或 1-based 索引（留空则合并顶部非背景图层）
        """
        backup_ase_file(session_manager, session_id)
        return _run_layer_script(session_id, "merge_down.lua", {
            "layer": str(layer),
        })

    @mcp.tool
    def flatten_layers(session_id: str) -> dict:
        """平面化所有图层（合并为单层）。

        Args:
            session_id: 会话 ID
        """
        backup_ase_file(session_manager, session_id)
        return _run_layer_script(session_id, "flatten.lua", {})

    @mcp.tool
    def duplicate_layer(session_id: str, layer: str = "") -> dict:
        """复制指定图层。不指定则复制当前活跃图层。

        Args:
            session_id: 会话 ID
            layer: 图层名称或 1-based 索引（留空则复制顶部图层）
        """
        return _run_layer_script(session_id, "duplicate_layer.lua", {
            "layer": str(layer),
        })
