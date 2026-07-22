"""Tileset 工具测试。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.tileset_tools import register_tileset_tools


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
    register_tileset_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_create_tileset_canvas_calls_script(setup):
    tools, _, runner = setup
    result = tools["create_tileset_canvas"](
        session_id="s1", tile_size=16, cols=6, rows=3
    )
    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "create_tileset.lua"
    params = call_args[0][1]
    assert params["tile_size"] == "16"
    assert params["cols"] == "6"


def test_create_tileset_canvas_rejects_bad_size(setup):
    tools, _, _ = setup
    result = tools["create_tileset_canvas"](
        session_id="s1", tile_size=20, cols=2, rows=2
    )
    assert result["success"] is False


def test_export_tiled_preview_returns_image(setup):
    tools, _, runner = setup
    with pytest.MonkeyPatch.context() as mp:
        # Image 需要文件存在，mock 它
        import src.tools.tileset_tools as mod
        mock_image = MagicMock()
        mp.setattr(mod, "Image", mock_image)
        result = tools["export_tiled_preview"](session_id="s1", repeat=2)
        assert mock_image.called
