"""动画工具：帧管理与导出。

提供帧的增删改查、帧持续时间设置、GIF 导出和精灵表导出功能。
每个工具调用对应的 Lua 脚本，通过 Aseprite CLI 执行操作。
"""

from fastmcp.utilities.types import Image

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.resources import _TIMING_PRESETS
from src.tools.utils import parse_json_output, run_script_with_file, validate_session_id


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
        """执行动画脚本（委托 utils.run_script_with_file）。"""
        return run_script_with_file(
            runner, session_manager, session_id, script_name, params,
            error_label="Animation operation failed",
        )

    @mcp.tool
    def add_frame(session_id: str, content: str = "copy") -> dict:
        """添加新帧（复制最后一帧或创建空白帧）。适合需要逐帧精细控制时使用。

        多帧批量绘制推荐用 draw_animation_frames 一次完成建帧+绘制。

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
        """设置单帧持续时间。适合微调某一帧的时长。

        所有帧统一时长推荐用 apply_timing_preset 批量设置。

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
        result = runner.run_script("get_frame_info.lua", {"file": str(ase_path)})
        data, error = parse_json_output(result, "Failed to get frame info")
        if error:
            return error
        return {"success": True, **data}

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
        """按动画类型批量设置所有帧时长（一次调用，替代逐帧 set_frame_duration）。

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
        info, info_error = parse_json_output(info_result, "Failed to get frame info")
        if info_error:
            return info_error
        # get_frame_info.lua 返回 frame_count(整数) + frames(数组)，取 frame_count
        frame_total = info.get("frame_count", 0)

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
        """一次绘制多帧动画（建帧+绘制一步完成），替代逐个 add_frame+draw_from_grid。
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

    @mcp.tool
    def duplicate_frame(session_id: str, frame: int) -> dict:
        """复制指定帧（在其后插入副本）。

        Args:
            session_id: 会话 ID
            frame: 要复制的帧号（1-based）
        """
        validate_session_id(session_id)
        if frame < 1:
            return {"success": False, "error": "frame must be >= 1"}
        return _run_anim_script(session_id, "duplicate_frame.lua", {
            "frame": str(frame),
        })

    # ===== 动画帧间一致性工具（帧继承 + 补间 + 差异验证）=====

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def compare_frames(session_id: str, frame_a: int = 1, frame_b: int = 2) -> dict:
        """比较两帧像素差异，返回量化报告（变化像素数/占比/变化区域包围盒/分图层变化）。

        动画一致性核心验证工具：帧间变化必须"只该动的像素动"。
        - changed_pct 过大 → 帧间脱节或画错区域
        - changed_pct 过小（接近 0）→ 动作没生效
        - bbox 可定位变化区域；layers 可定位是哪个图层在变

        Args:
            session_id: 会话 ID
            frame_a: 帧 A（1-based，默认 1）
            frame_b: 帧 B（1-based，默认 2）
        """
        validate_session_id(session_id)
        if frame_a < 1 or frame_b < 1:
            return {"success": False, "error": "frame_a and frame_b must be >= 1"}
        if frame_a == frame_b:
            return {"success": False, "error": "frame_a and frame_b must be different"}
        ase_path = session_manager.get_ase_path(session_id)
        result = runner.run_script("compare_frames.lua", {
            "file": str(ase_path),
            "frame_a": str(frame_a),
            "frame_b": str(frame_b),
        })
        data, error = parse_json_output(result, "Failed to compare frames")
        if error:
            return error
        return {"success": True, **data}

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def export_contact_sheet(
        session_id: str,
        start_frame: int = 1,
        end_frame: int = 0,
        columns: int = 0,
        ghost: bool = True,
        scale: int = 4,
    ) -> Image:
        """导出多帧动画总览图（contact sheet）：全部帧拼一张大图返回。

        替代逐帧 get_canvas_preview 的低效方式，一次看完整条动画的连贯性。
        ghost=True 时每帧下方叠加前一帧的红色半透明轮廓，帧间差异一目了然。

        Args:
            session_id: 会话 ID
            start_frame: 起始帧（1-based，默认 1）
            end_frame: 结束帧（1-based，默认 0=最后一帧）
            columns: 每行帧数（0=单行横排，默认 0）
            ghost: 是否叠加前一帧幽灵轮廓（默认 True）
            scale: 放大倍数（默认 4）
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        png_path = work_dir / "contact_sheet.png"

        result = runner.run_script("export_contact_sheet.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "start_frame": str(start_frame),
            "end_frame": str(end_frame),
            "columns": str(columns),
            "ghost": "1" if ghost else "0",
            "scale": str(scale),
        })
        if not result["success"]:
            raise RuntimeError(
                f"Failed to export contact sheet: {result.get('error', 'Unknown')}"
            )
        return Image(path=str(png_path))

    @mcp.tool
    def propagate_cels(
        session_id: str, layer: str, source_frame: int = 1, to_frame: int = 0
    ) -> dict:
        """把指定图层某帧的 cel 复制到后续帧范围（"换姿势不换画"核心）。

        先画好基础身体/背景层，复制到整个帧范围，肢体层再逐帧独立编辑。
        静态部分帧间零差异由构造保证，不会漂移。

        Args:
            session_id: 会话 ID
            layer: 图层名或索引（如 "Body" 或 "1"）
            source_frame: 源帧（1-based，默认 1）
            to_frame: 目标末帧（1-based 包含，默认 0=最后一帧，须 > source_frame）
        """
        return _run_anim_script(session_id, "propagate_cels.lua", {
            "layer": str(layer),
            "source_frame": str(source_frame),
            "to_frame": str(to_frame),
        })

    @mcp.tool
    def tween_cel_positions(
        session_id: str,
        layer: str,
        from_frame: int,
        to_frame: int,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
    ) -> dict:
        """线性补间 cel 位置（如挥剑轨迹、平移动作）。

        帧间坐标由数学插值保证，不会出现手绘补间的抖动。首末帧精确等于起止值。

        Args:
            session_id: 会话 ID
            layer: 图层名或索引
            from_frame: 起始帧（1-based）
            to_frame: 结束帧（1-based，须 > from_frame）
            start_x/start_y: 起始坐标（cel 左上角）
            end_x/end_y: 结束坐标
        """
        return _run_anim_script(session_id, "tween_cel.lua", {
            "layer": str(layer),
            "from_frame": str(from_frame),
            "to_frame": str(to_frame),
            "property": "pos",
            "start_x": str(start_x),
            "start_y": str(start_y),
            "end_x": str(end_x),
            "end_y": str(end_y),
        })

    @mcp.tool
    def tween_cel_scale(
        session_id: str,
        layer: str,
        from_frame: int,
        to_frame: int,
        start_scale: float = 1.0,
        end_scale: float = 1.0,
    ) -> dict:
        """线性补间 cel 缩放（以原始中心为锚点，如呼吸起伏、压扁拉伸）。

        Args:
            session_id: 会话 ID
            layer: 图层名或索引
            from_frame: 起始帧（1-based）
            to_frame: 结束帧（1-based，须 > from_frame）
            start_scale: 起始缩放比例（1.0=原始尺寸）
            end_scale: 结束缩放比例
        """
        return _run_anim_script(session_id, "tween_cel.lua", {
            "layer": str(layer),
            "from_frame": str(from_frame),
            "to_frame": str(to_frame),
            "property": "scale",
            "start_scale": str(start_scale),
            "end_scale": str(end_scale),
        })

    @mcp.tool
    def tween_cel_opacity(
        session_id: str,
        layer: str,
        from_frame: int,
        to_frame: int,
        start_opacity: int = 255,
        end_opacity: int = 0,
    ) -> dict:
        """线性补间 cel 不透明度（0-255，如淡入淡出、消散效果）。

        Args:
            session_id: 会话 ID
            layer: 图层名或索引
            from_frame: 起始帧（1-based）
            to_frame: 结束帧（1-based，须 > from_frame）
            start_opacity: 起始不透明度（0-255，默认 255）
            end_opacity: 结束不透明度（0-255，默认 0）
        """
        return _run_anim_script(session_id, "tween_cel.lua", {
            "layer": str(layer),
            "from_frame": str(from_frame),
            "to_frame": str(to_frame),
            "property": "opacity",
            "start_opacity": str(start_opacity),
            "end_opacity": str(end_opacity),
        })
