"""动画辅助增强工具测试。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.tools.animation_tools import register_animation_tools


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool
    register_animation_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_apply_timing_preset_calls_batch_script(setup):
    """apply_timing_preset 应调用 set_frame_durations.lua（批量）。

    mock 数据必须匹配 get_frame_info.lua 的真实返回格式：
    {"frame_count": N, "frames": [{frame_number, duration}, ...]}
    frames 是数组而非整数，frame_count 才是帧数。
    """
    tools, sm, runner = setup
    # get_frame_info 返回真实格式：frame_count(整数) + frames(数组)
    runner.run_script.side_effect = [
        {"success": True, "stdout": '{"frame_count": 4, "frames": [{"frame_number": 1, "duration": 0.1}, {"frame_number": 2, "duration": 0.1}, {"frame_number": 3, "duration": 0.1}, {"frame_number": 4, "duration": 0.1}]}', "stderr": ""},
        {"success": True, "stdout": "OK", "stderr": ""},
    ]
    result = tools["apply_timing_preset"](session_id="s1", animation_type="walk")
    assert result["success"] is True
    # 第二次调用应是 set_frame_durations.lua
    last_call = runner.run_script.call_args_list[-1]
    assert last_call[0][0] == "set_frame_durations.lua"
    # 验证 durations 参数是 4 个 125ms（walk 预设），逗号分隔
    durations_param = last_call[0][1]["durations"]
    assert durations_param == "125,125,125,125"


def test_apply_timing_preset_rejects_unknown_type(setup):
    tools, _, _ = setup
    result = tools["apply_timing_preset"](session_id="s1", animation_type="fly")
    assert result["success"] is False


def test_draw_animation_frames_calls_script(setup):
    """draw_animation_frames 应调用 draw_animation_frames.lua。"""
    tools, _, runner = setup
    result = tools["draw_animation_frames"](
        session_id="s1",
        grids="RRR/RRR/RRR|GGG/GGG/GGG",
        colormap="R=#FF0000,G=#00FF00,.=transparent",
    )
    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "draw_animation_frames.lua"


def test_export_onion_skin_preview_returns_image(setup):
    """export_onion_skin_preview 应返回 Image 对象。"""
    tools, sm, runner = setup
    with patch("src.tools.animation_tools.Image") as mock_image:
        mock_inst = MagicMock()
        mock_image.return_value = mock_inst
        result = tools["export_onion_skin_preview"](session_id="s1", frame=2)
        assert result is mock_inst
