"""绘制原语工具测试。"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from src.tools.draw_tools import register_draw_tools


@pytest.fixture
def setup():
    """提供 mock 依赖。"""
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
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

    register_draw_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_draw_pixel_calls_correct_script(setup):
    """测试 draw_pixel 调用 draw_pixel.lua 并传递正确参数。"""
    tools, session_manager, runner = setup

    result = tools["draw_pixel"](
        session_id="s1", x=5, y=10, color="#FF0000"
    )

    runner.run_script.assert_called_once_with(
        "draw_pixel.lua",
        {"file": str(Path("/tmp/canvas.ase")), "x": "5", "y": "10", "color": "#FF0000"},
    )
    assert result["success"] is True


def test_draw_pixel_invalid_color(setup):
    """测试无效颜色抛出 ValueError。"""
    tools, session_manager, runner = setup

    with pytest.raises(ValueError, match="Invalid color"):
        tools["draw_pixel"](
            session_id="s1", x=5, y=10, color="FF0000"
        )


def test_draw_line_calls_correct_script(setup):
    """测试 draw_line 调用 draw_line.lua。"""
    tools, session_manager, runner = setup

    result = tools["draw_line"](
        session_id="s1", x1=0, y1=0, x2=15, y2=15, color="#00FF00"
    )

    runner.run_script.assert_called_once_with(
        "draw_line.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "x1": "0", "y1": "0", "x2": "15", "y2": "15",
            "color": "#00FF00",
        },
    )
    assert result["success"] is True


def test_draw_rect_default_not_filled(setup):
    """测试 draw_rect 默认不填充。"""
    tools, session_manager, runner = setup

    tools["draw_rect"](
        session_id="s1", x=0, y=0, width=10, height=10, color="#0000FF"
    )

    call_args = runner.run_script.call_args
    assert call_args[0][1]["filled"] == "false"


def test_draw_rect_filled_true(setup):
    """测试 draw_rect 填充模式。"""
    tools, session_manager, runner = setup

    tools["draw_rect"](
        session_id="s1", x=0, y=0, width=10, height=10,
        color="#0000FF", filled=True
    )

    call_args = runner.run_script.call_args
    assert call_args[0][1]["filled"] == "true"


def test_draw_ellipse_calls_correct_script(setup):
    """测试 draw_ellipse 调用 draw_ellipse.lua。"""
    tools, session_manager, runner = setup

    result = tools["draw_ellipse"](
        session_id="s1", cx=8, cy=8, rx=5, ry=5, color="#FF00FF"
    )

    runner.run_script.assert_called_once_with(
        "draw_ellipse.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "cx": "8", "cy": "8", "rx": "5", "ry": "5",
            "color": "#FF00FF", "filled": "false",
        },
    )
    assert result["success"] is True


def test_fill_region_calls_correct_script(setup):
    """测试 fill_region 调用 fill_region.lua。"""
    tools, session_manager, runner = setup

    result = tools["fill_region"](
        session_id="s1", x=5, y=5, color="#FFFFFF"
    )

    runner.run_script.assert_called_once_with(
        "fill_region.lua",
        {"file": str(Path("/tmp/canvas.ase")), "x": "5", "y": "5", "color": "#FFFFFF"},
    )
    assert result["success"] is True


def test_clear_region_calls_correct_script(setup):
    """测试 clear_region 调用 clear_region.lua。"""
    tools, session_manager, runner = setup

    result = tools["clear_region"](
        session_id="s1", x=0, y=0, width=5, height=5
    )

    runner.run_script.assert_called_once_with(
        "clear_region.lua",
        {
            "file": str(Path("/tmp/canvas.ase")),
            "x": "0", "y": "0", "width": "5", "height": "5",
        },
    )
    assert result["success"] is True


def test_clear_canvas_calls_correct_script(setup):
    """测试 clear_canvas 调用 clear_canvas.lua。"""
    tools, session_manager, runner = setup

    result = tools["clear_canvas"](session_id="s1")

    runner.run_script.assert_called_once_with(
        "clear_canvas.lua",
        {"file": str(Path("/tmp/canvas.ase"))},
    )
    assert result["success"] is True


def test_draw_tool_handles_failure(setup):
    """测试绘制失败时返回错误。"""
    tools, session_manager, runner = setup
    runner.run_script.return_value = {
        "success": False, "stdout": "", "stderr": "ERROR", "error": "failed"
    }

    result = tools["draw_pixel"](
        session_id="s1", x=5, y=10, color="#FF0000"
    )

    assert result["success"] is False
    assert "error" in result
