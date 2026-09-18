"""颜色调整工具测试。"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func
    mcp.tool = capture_tool

    from src.tools.color_adjustment_tools import register_color_adjustment_tools
    register_color_adjustment_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_adjust_colors_all_defaults(setup):
    tools, session_manager, runner = setup
    result = tools["adjust_colors"](session_id="s1")
    assert result["success"] is True
    runner.run_script.assert_called_once()
    assert runner.run_script.call_args[0][0] == "adjust_colors.lua"


def test_adjust_colors_brightness(setup):
    tools, session_manager, runner = setup
    result = tools["adjust_colors"](session_id="s1", brightness=50)
    assert result["success"] is True
    params = runner.run_script.call_args[0][1]
    assert params["brightness"] == "50"


def test_adjust_colors_hue(setup):
    tools, session_manager, runner = setup
    result = tools["adjust_colors"](session_id="s1", hue=90)
    assert result["success"] is True
    params = runner.run_script.call_args[0][1]
    assert params["hue"] == "90"


def test_adjust_colors_invalid_brightness(setup):
    tools, session_manager, runner = setup
    result = tools["adjust_colors"](session_id="s1", brightness=200)
    assert result["success"] is False


def test_adjust_colors_invalid_hue(setup):
    tools, session_manager, runner = setup
    result = tools["adjust_colors"](session_id="s1", hue=999)
    assert result["success"] is False


def test_adjust_colors_invalid_contrast(setup):
    tools, session_manager, runner = setup
    result = tools["adjust_colors"](session_id="s1", contrast=150)
    assert result["success"] is False


def test_adjust_colors_combined(setup):
    tools, session_manager, runner = setup
    result = tools["adjust_colors"](
        session_id="s1", brightness=10, contrast=20, hue=-30, saturation=40, lightness=-10
    )
    assert result["success"] is True
    params = runner.run_script.call_args[0][1]
    assert params["brightness"] == "10"
    assert params["contrast"] == "20"
    assert params["hue"] == "-30"
    assert params["saturation"] == "40"
    assert params["lightness"] == "-10"
