"""调色板工具：设置颜色、获取调色板、调整大小、加载调色板。

每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行调色板操作。
"""

import json

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.resources import _PRESET_PALETTES
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

    # ===== 调色板增强工具（docs §4）=====

    # 预设调色板名称白名单
    _PRESET_NAMES = set(_PRESET_PALETTES.keys())

    @mcp.tool
    def apply_preset_palette(session_id: str, preset_name: str) -> dict:
        """★批量★ 应用内置预设调色板到画布（整板替换）。

        一次调用写入整个预设调色板，替代 N 次 set_palette_color。
        可用预设: db16(16色), db32(32色), aap64(64色), nes(NES复古), gameboy(4色绿)。

        Args:
            session_id: 会话 ID
            preset_name: 预设名（db16/db32/aap64/nes/gameboy）
        """
        # 校验预设名是否在白名单内
        if preset_name not in _PRESET_NAMES:
            return {
                "success": False,
                "error": f"Unknown preset: {preset_name}. Available: {sorted(_PRESET_NAMES)}",
            }
        # 从预设字典取出色值列表，拼接为逗号分隔字符串
        colors = _PRESET_PALETTES[preset_name]["colors"]
        return _run_palette_script(session_id, "apply_palette.lua", {
            "colors": ",".join(colors),
        })

    @mcp.tool
    def append_palette_colors(session_id: str, colors: str) -> dict:
        """★批量★ 一次追加多个颜色到调色板末尾，替代 N 次 set_palette_color 循环。

        ⚠️ 不要循环调用 set_palette_color，N 个颜色请用本工具一次完成。

        Args:
            session_id: 会话 ID
            colors: 逗号分隔的 #RRGGBB 列表，如 "#FF0000,#00FF00,#0000FF"
        """
        return _run_palette_script(session_id, "append_palette.lua", {
            "colors": colors,
        })

    @mcp.tool
    def derive_shading_palette(
        base_color: str,
        shades: int = 5,
        hue_shift: bool = True,
        apply_to_palette: bool = True,
        session_id: str = None,
    ) -> dict:
        """按 docs §3.4/§4.4 公式从主色派生专业三阶配色（高光/主色/阴影/深阴影/轮廓）。

        色相偏移：暗部偏冷(蓝)、亮部偏暖(黄)，避免业余的"发灰"配色。
        默认 apply_to_palette=true，自动追加到调色板（1 次 append_palette_colors 调用）。

        Args:
            base_color: 主色 #RRGGBB
            shades: 返回色阶数（默认 5）
            hue_shift: 是否启用色相偏移（默认 true，关闭则纯亮度缩放）
            apply_to_palette: 是否追加到调色板（默认 true，需提供 session_id）
            session_id: 会话 ID（apply_to_palette=true 时必填）
        """
        # 校验主色格式
        color = validate_color(base_color)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        # 色相偏移强度（关闭时为 0，即纯亮度缩放）
        k = 20 if hue_shift else 0

        def clamp(v):
            return max(0, min(255, round(v)))

        # 高光：亮部偏暖（R 增幅大，B 降），×1.3
        highlight = f"#{clamp(r*1.3 + k):02X}{clamp(g*1.3 + k*0.3):02X}{clamp(b*1.3 - k):02X}"
        base = f"#{r:02X}{g:02X}{b:02X}"
        # 阴影：暗部偏冷（B 增幅大，R 降），×0.7
        shadow = f"#{clamp(r*0.7 - k*0.3):02X}{clamp(g*0.7):02X}{clamp(b*0.7 + k):02X}"
        # 深阴影：×0.5
        deep_shadow = f"#{clamp(r*0.5):02X}{clamp(g*0.5):02X}{clamp(b*0.5 + k*0.5):02X}"
        outline = "#000000"

        # 按从亮到暗顺序排列，截取前 shades 个
        all_shades = [highlight, base, shadow, deep_shadow, outline][:shades]

        if apply_to_palette:
            if not session_id:
                return {"success": False, "error": "session_id is required when apply_to_palette=true"}
            # 复用 append_palette_colors 一次性追加（批量优化关键）
            append_result = append_palette_colors(session_id, ",".join(all_shades))
            if not append_result["success"]:
                return append_result

        return {"success": True, "colors_hex": all_shades}
