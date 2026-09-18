"""动画帧间一致性工具测试。

验证 compare_frames / export_contact_sheet / propagate_cels / tween_cel_*
工具的正确脚本名与参数传递（mock runner，不依赖真实 Aseprite）。
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.tools.animation_tools import register_animation_tools


@pytest.fixture
def setup():
    """提供 mock 依赖。"""
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")
    runner.run_script.return_value = {
        "success": True, "stdout": "OK", "stderr": ""
    }

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


def test_compare_frames_calls_correct_script(setup):
    """测试 compare_frames 调用 compare_frames.lua 并解析 JSON 输出。"""
    tools, session_manager, runner = setup
    runner.run_script.return_value = {
        "success": True,
        "stdout": '{"frame_a": 1, "frame_b": 2, "total_pixels": 1024, '
                  '"changed_pixels": 32, "changed_pct": 3.12, '
                  '"bbox": {"x": 4, "y": 8, "width": 8, "height": 6}, "layers": []}',
        "stderr": "",
    }

    result = tools["compare_frames"](session_id="s1", frame_a=1, frame_b=2)

    runner.run_script.assert_called_once_with(
        "compare_frames.lua",
        {"file": str(Path("/tmp/canvas.ase")), "frame_a": "1", "frame_b": "2"},
    )
    assert result["success"] is True
    assert result["changed_pixels"] == 32
    assert result["changed_pct"] == 3.12


def test_compare_frames_rejects_same_frames(setup):
    """测试相同帧号返回错误。"""
    tools, _, _ = setup
    result = tools["compare_frames"](session_id="s1", frame_a=1, frame_b=1)
    assert result["success"] is False


def test_compare_frames_handles_script_failure(setup):
    """测试脚本失败时返回错误信息。"""
    tools, _, runner = setup
    runner.run_script.return_value = {
        "success": False, "stdout": "", "stderr": "boom", "error": "failed"
    }
    result = tools["compare_frames"](session_id="s1", frame_a=1, frame_b=2)
    assert result["success"] is False
    assert "error" in result


def test_export_contact_sheet_calls_correct_script(setup):
    """测试 export_contact_sheet 调用 export_contact_sheet.lua 并返回 Image。"""
    tools, session_manager, runner = setup

    result = tools["export_contact_sheet"](
        session_id="s1", start_frame=1, end_frame=0, columns=0,
        ghost=True, scale=4,
    )

    runner.run_script.assert_called_once_with(
        "export_contact_sheet.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "output": str(Path("/tmp/work/contact_sheet.png")),
            "start_frame": "1",
            "end_frame": "0",
            "columns": "0",
            "ghost": "1",
            "scale": "4",
        },
    )
    assert str(result.path).endswith("contact_sheet.png")


def test_export_contact_sheet_no_ghost(setup):
    """测试 ghost=False 时传 ghost=0。"""
    tools, _, runner = setup

    tools["export_contact_sheet"](session_id="s1", ghost=False)

    call_args = runner.run_script.call_args
    assert call_args[0][1]["ghost"] == "0"


def test_propagate_cels_calls_correct_script(setup):
    """测试 propagate_cels 调用 propagate_cels.lua 并传递参数。"""
    tools, _, runner = setup

    result = tools["propagate_cels"](
        session_id="s1", layer="Body", source_frame=1, to_frame=4
    )

    runner.run_script.assert_called_once_with(
        "propagate_cels.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "layer": "Body",
            "source_frame": "1",
            "to_frame": "4",
        },
    )
    assert result["success"] is True


def test_tween_cel_positions_calls_correct_script(setup):
    """测试 tween_cel_positions 调用 tween_cel.lua（property=pos）。"""
    tools, _, runner = setup

    tools["tween_cel_positions"](
        session_id="s1", layer="Sword", from_frame=1, to_frame=4,
        start_x=0, start_y=0, end_x=8, end_y=0,
    )

    runner.run_script.assert_called_once_with(
        "tween_cel.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "layer": "Sword",
            "from_frame": "1",
            "to_frame": "4",
            "property": "pos",
            "start_x": "0", "start_y": "0",
            "end_x": "8", "end_y": "0",
        },
    )


def test_tween_cel_scale_calls_correct_script(setup):
    """测试 tween_cel_scale 调用 tween_cel.lua（property=scale）。"""
    tools, _, runner = setup

    tools["tween_cel_scale"](
        session_id="s1", layer="Body", from_frame=1, to_frame=4,
        start_scale=1.0, end_scale=0.8,
    )

    runner.run_script.assert_called_once_with(
        "tween_cel.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "layer": "Body",
            "from_frame": "1",
            "to_frame": "4",
            "property": "scale",
            "start_scale": "1.0",
            "end_scale": "0.8",
        },
    )


def test_tween_cel_opacity_calls_correct_script(setup):
    """测试 tween_cel_opacity 调用 tween_cel.lua（property=opacity）。"""
    tools, _, runner = setup

    tools["tween_cel_opacity"](
        session_id="s1", layer="Glow", from_frame=1, to_frame=4,
        start_opacity=255, end_opacity=0,
    )

    runner.run_script.assert_called_once_with(
        "tween_cel.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "layer": "Glow",
            "from_frame": "1",
            "to_frame": "4",
            "property": "opacity",
            "start_opacity": "255",
            "end_opacity": "0",
        },
    )


def test_tween_cel_handles_failure(setup):
    """测试补间脚本失败时返回错误。"""
    tools, _, runner = setup
    runner.run_script.return_value = {
        "success": False, "stdout": "", "stderr": "boom", "error": "failed"
    }
    result = tools["tween_cel_positions"](
        session_id="s1", layer="Sword", from_frame=1, to_frame=4,
        start_x=0, start_y=0, end_x=8, end_y=0,
    )
    assert result["success"] is False
    assert "error" in result
