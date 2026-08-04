"""滤镜工具测试。"""

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

    from src.tools.filter_tools import register_filter_tools
    register_filter_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_apply_blur_defaults(setup):
    tools, session_manager, runner = setup
    result = tools["apply_blur"](session_id="s1")
    assert result["success"] is True
    runner.run_script.assert_called_once()
    assert runner.run_script.call_args[0][0] == "apply_blur.lua"


def test_apply_blur_custom_params(setup):
    tools, session_manager, runner = setup
    result = tools["apply_blur"](session_id="s1", radius=2, strength=3)
    assert result["success"] is True
    params = runner.run_script.call_args[0][1]
    assert params["radius"] == "2"
    assert params["strength"] == "3"


def test_apply_blur_invalid_radius(setup):
    tools, session_manager, runner = setup
    result = tools["apply_blur"](session_id="s1", radius=5)
    assert result["success"] is False


def test_apply_blur_invalid_strength(setup):
    tools, session_manager, runner = setup
    result = tools["apply_blur"](session_id="s1", strength=0)
    assert result["success"] is False


def test_apply_blur_handles_failure(setup):
    tools, session_manager, runner = setup
    runner.run_script.return_value = {"success": False, "stdout": "", "stderr": "err", "error": "failed"}
    result = tools["apply_blur"](session_id="s1")
    assert result["success"] is False
