"""质量检查工具测试。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.quality_tools import register_quality_tools


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool
    register_quality_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_check_canvas_standards_parses_json(setup):
    """check_canvas_standards 应解析 Lua 返回的 JSON 报告。"""
    tools, _, runner = setup
    runner.run_script.return_value = {
        "success": True,
        "stdout": '{"success": true, "checks": {"size": {"pass": true, "detail": "16x16", "suggestion": "x"}}, "stats": {"width": 16, "height": 16, "color_count": 5, "frames": 1}}',
        "stderr": "",
    }
    result = tools["check_canvas_standards"](session_id="s1")
    assert result["success"] is True
    assert result["stats"]["color_count"] == 5


def test_check_canvas_standards_handles_error(setup):
    tools, _, runner = setup
    runner.run_script.return_value = {
        "success": True, "stdout": '{"error": "cannot open file"}', "stderr": "",
    }
    result = tools["check_canvas_standards"](session_id="s1")
    assert result["success"] is False


def test_export_silhouette_returns_image(setup):
    tools, _, runner = setup
    with pytest.MonkeyPatch.context() as mp:
        import src.tools.quality_tools as mod
        mock_image = MagicMock()
        mp.setattr(mod, "Image", mock_image)
        result = tools["export_silhouette"](session_id="s1")
        assert mock_image.called
