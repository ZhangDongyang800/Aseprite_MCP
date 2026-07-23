"""动画工具：帧管理与导出。

提供帧的增删改查、帧持续时间设置、GIF 导出和精灵表导出功能。
每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行操作。
"""

import json
from pathlib import Path

from fastmcp.utilities.types import Image

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.resources import _TIMING_PRESETS
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
        """⚠️ 勿循环调用建多帧动画，多帧请用 draw_animation_frames 一次完成建帧+绘制。

        添加新帧（复制最后一帧或创建空白帧）。

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
        """⚠️ 勿逐帧循环调用，多帧请用 apply_timing_preset 批量设置。

        设置帧持续时间。

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

    # ===== 动画辅助增强工具（docs §7）=====

    # 预设动画类型白名单（从 _TIMING_PRESETS 派生）
    _TIMING_TYPES = set(_TIMING_PRESETS.keys())

    @mcp.tool
    def apply_timing_preset(
        session_id: str, animation_type: str, frame_count: int = None
    ) -> dict:
        """★批量★ 按动画类型批量设置所有帧时长，替代 N 次 set_frame_duration。

        ⚠️ 不要逐帧调用 set_frame_duration，本工具一次设置所有帧时长。
        docs §7.2：不同动作用不同时长是专业动画关键。
        可用类型: idle(400ms), walk(125ms), run(80ms), attack_hit(160ms) 等。

        Args:
            session_id: 会话 ID
            animation_type: 动画类型（见 aseprite://timing/presets）
            frame_count: 实际帧数（可选，与建议范围不符时返回警告）
        """
        # 校验动画类型是否在预设白名单内
        if animation_type not in _TIMING_TYPES:
            return {
                "success": False,
                "error": f"Unknown type: {animation_type}. Available: {sorted(_TIMING_TYPES)}",
            }
        preset = _TIMING_PRESETS[animation_type]
        duration_ms = preset["duration_ms"]

        # 先获取当前帧数（用于构造等长 durations 列表）
        info_result = runner.run_script("get_frame_info.lua", {
            "file": str(session_manager.get_ase_path(session_id)),
        })
        try:
            info = json.loads(info_result["stdout"].strip())
            # get_frame_info.lua 返回 frame_count(整数) + frames(数组)，取 frame_count
            frame_total = info.get("frame_count", 0)
        except (json.JSONDecodeError, KeyError):
            return {"success": False, "error": "Failed to get frame info"}

        if frame_total == 0:
            return {"success": False, "error": "No frames in canvas"}

        # 构造等长 durations 列表（逗号分隔的毫秒值）
        durations = ",".join([str(duration_ms)] * frame_total)

        # 帧数与建议范围不符则警告（不阻断执行）
        warning = ""
        if frame_count is not None:
            lo, hi = preset["frame_count_range"]
            if not (lo <= frame_count <= hi):
                warning = f"Warning: frame_count {frame_count} outside suggested range [{lo},{hi}]"

        # 批量调用 set_frame_durations.lua 一次设置所有帧时长
        result = _run_anim_script(session_id, "set_frame_durations.lua", {
            "durations": durations,
        })
        if warning:
            result["warning"] = warning
        return result

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def export_onion_skin_preview(session_id: str, frame: int = 1, scale: int = 4) -> Image:
        """导出洋葱皮叠加预览：当前帧(原色)+前一帧(红)+后一帧(蓝)。

        给 AI "洋葱皮眼睛"检查动画连贯性（docs §7.4/§11.3）。
        第 1 帧无前一帧、末帧无后一帧，仅叠加存在的帧。

        Args:
            session_id: 会话 ID
            frame: 中心帧号（1-indexed，默认 1）
            scale: 放大倍数（默认 4）
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        png_path = work_dir / f"onion_{frame}.png"

        # 调用 Lua 脚本生成洋葱皮叠加 PNG
        result = runner.run_script("export_onion_skin.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "frame": str(frame),
            "scale": str(scale),
        })
        if not result["success"]:
            raise RuntimeError(
                f"Failed to export onion skin: {result.get('error', 'Unknown')}"
            )
        # 返回 Image 对象（FastMCP 自动 base64 编码）
        return Image(path=str(png_path))

    @mcp.tool
    def draw_animation_frames(
        session_id: str, grids: str, colormap: str,
        mode: str = "copy", layer: int = 1,
    ) -> dict:
        """★批量★ 一次绘制多帧动画，替代 N 次 add_frame+clear+draw_from_grid 循环。

        ⚠️ 不要逐帧调用 add_frame+draw_from_grid，本工具一次完成所有帧。
        6 帧动画从约 20 次调用降到 1 次。
        grids 用 | 分隔每帧，帧内行用 / 分隔。
        例: grids="RRR/RRR|GGG/GGG" 表示 2 帧各 2 行。
        mode="copy" 新帧复制上一帧再绘 grid（推荐，适合局部变化）；
        mode="blank" 新帧空白再绘 grid。

        Args:
            session_id: 会话 ID
            grids: 多帧 grid，用 | 分隔帧，/ 分隔行
            colormap: 颜色映射，如 "R=#FF0000,.=transparent"
            mode: 建帧模式 copy/blank（默认 copy）
            layer: 目标图层（默认 1）
        """
        # 参数校验：grids 和 colormap 必填
        if not grids or not colormap:
            return {"success": False, "error": "grids and colormap are required"}
        # mode 只允许 copy 或 blank
        if mode not in ("copy", "blank"):
            return {"success": False, "error": f"Invalid mode: {mode}. Use 'copy' or 'blank'"}
        return _run_anim_script(session_id, "draw_animation_frames.lua", {
            "grids": grids, "colormap": colormap, "mode": mode, "layer": str(layer),
        })
