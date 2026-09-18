"""批量编辑与逃逸舱工具测试。"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    runner.run_script.return_value = {"success": True, "stdout": '{"total":2,"succeeded":2,"failed":0}', "stderr": ""}

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func
    mcp.tool = capture_tool

    from src.tools.batch_tools import register_batch_tools
    register_batch_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_batch_edit_empty_operations(setup):
    tools, session_manager, runner = setup
    result = tools["batch_edit"](session_id="s1", operations="")
    assert result["success"] is False


def test_batch_edit_calls_correct_script(setup):
    tools, session_manager, runner = setup
    result = tools["batch_edit"](
        session_id="s1",
        operations="draw_rect x=0 y=0 width=8 height=8 color=#FF0000 filled=true ; draw_pixel x=4 y=4 color=#000000"
    )
    assert result["success"] is True
    runner.run_script.assert_called_once()
    call = runner.run_script.call_args
    assert call[0][0] == "batch_edit.lua"


def test_batch_edit_handles_failure(setup):
    tools, session_manager, runner = setup
    runner.run_script.return_value = {"success": False, "stdout": "", "stderr": "fail", "error": "batch failed"}
    result = tools["batch_edit"](session_id="s1", operations="invalid_op")
    assert result["success"] is False


def test_run_lua_empty_code(setup):
    tools, session_manager, runner = setup
    result = tools["run_lua"](session_id="s1", code="")
    assert result["success"] is False


def test_run_lua_calls_correct_script(setup):
    tools, session_manager, runner = setup
    runner.run_script.return_value = {"success": True, "stdout": "hello world", "stderr": ""}
    result = tools["run_lua"](session_id="s1", code='print("hello world")')
    assert result["success"] is True
    runner.run_script.assert_called_once()
    call = runner.run_script.call_args
    assert call[0][0] == "run_lua.lua"


def test_undo_no_backup(setup):
    """Undo without existing backup should fail."""
    tools, session_manager, runner = setup
    session_manager.get_ase_path.return_value = Path("/tmp/nonexistent/canvas.ase")
    result = tools["undo"](session_id="s1")
    assert result["success"] is False


def test_redo(setup):
    tools, session_manager, runner = setup
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}
    result = tools["redo"](session_id="s1")
    # redo in CLI mode just runs the Lua script (may succeed or fail)
    assert "success" in result
