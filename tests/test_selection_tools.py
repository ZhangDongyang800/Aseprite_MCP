"""选区工具测试。"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp")
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func
    mcp.tool = capture_tool

    from src.tools.selection_tools import register_selection_tools
    register_selection_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_select_all(setup):
    tools, session_manager, runner = setup
    result = tools["select_all"](session_id="s1")
    assert result["success"] is True
    runner.run_script.assert_called_once()
    assert runner.run_script.call_args[0][0] == "select_all.lua"


def test_deselect(setup):
    tools, session_manager, runner = setup
    result = tools["deselect"](session_id="s1")
    assert result["success"] is True
    runner.run_script.assert_called_once()
    assert runner.run_script.call_args[0][0] == "deselect.lua"


def test_select_by_color(setup):
    tools, session_manager, runner = setup
    result = tools["select_by_color"](session_id="s1", color="#FF0000", tolerance=10)
    assert result["success"] is True
    runner.run_script.assert_called_once()
    call = runner.run_script.call_args
    assert call[0][0] == "select_by_color.lua"
    assert call[0][1]["color"] == "#FF0000"
    assert call[0][1]["tolerance"] == "10"


def test_select_by_color_invalid_color(setup):
    tools, session_manager, runner = setup
    with pytest.raises(ValueError):
        tools["select_by_color"](session_id="s1", color="invalid")


def test_select_by_color_invalid_tolerance(setup):
    tools, session_manager, runner = setup
    result = tools["select_by_color"](session_id="s1", color="#FF0000", tolerance=300)
    assert result["success"] is False


def test_invert_selection(setup):
    tools, session_manager, runner = setup
    result = tools["invert_selection"](session_id="s1")
    assert result["success"] is True
    runner.run_script.assert_called_once()
    assert runner.run_script.call_args[0][0] == "invert_selection.lua"


def test_delete_selection(setup):
    tools, session_manager, runner = setup
    result = tools["delete_selection"](session_id="s1")
    assert result["success"] is True
    runner.run_script.assert_called_once()
    assert runner.run_script.call_args[0][0] == "delete_selection.lua"


def test_selection_handles_failure(setup):
    tools, session_manager, runner = setup
    runner.run_script.return_value = {"success": False, "stdout": "", "stderr": "fail", "error": "failed"}
    result = tools["select_all"](session_id="s1")
    assert result["success"] is False
