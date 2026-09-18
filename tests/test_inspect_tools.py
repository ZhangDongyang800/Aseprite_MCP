"""检查与导出工具测试。"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.tools.inspect_tools import register_inspect_tools


@pytest.fixture
def setup():
    """提供 mock 依赖。"""
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")
    session_manager.get_canvas_info.return_value = {
        "width": 16, "height": 16, "color_mode": "rgb"
    }
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

    register_inspect_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_get_canvas_info_returns_metadata(setup):
    """测试 get_canvas_info 返回画布元数据。"""
    tools, session_manager, runner = setup

    result = tools["get_canvas_info"](session_id="s1")

    assert result["width"] == 16
    assert result["height"] == 16
    assert result["color_mode"] == "rgb"


def test_get_canvas_preview_calls_export_script(setup):
    """测试 get_canvas_preview 调用 export_png.lua。"""
    tools, session_manager, runner = setup

    with patch("src.tools.inspect_tools.Image") as mock_image:
        mock_image_instance = MagicMock()
        mock_image.return_value = mock_image_instance

        tools["get_canvas_preview"](session_id="s1", scale=2)

        # 验证调用了 export_png.lua
        runner.run_script.assert_called_once_with(
            "export_png.lua",
            {
                "file": str(Path("/tmp/canvas.ase")),
                "output": str(Path("/tmp/work/preview.png")),
                "scale": "2",
            },
        )


def test_get_canvas_preview_default_scale(setup):
    """测试 get_canvas_preview 默认缩放为 1。"""
    tools, session_manager, runner = setup

    with patch("src.tools.inspect_tools.Image"):
        tools["get_canvas_preview"](session_id="s1")

        call_args = runner.run_script.call_args
        assert call_args[0][1]["scale"] == "1"


def test_get_canvas_preview_returns_image(setup):
    """测试 get_canvas_preview 返回 Image 对象。"""
    tools, session_manager, runner = setup

    with patch("src.tools.inspect_tools.Image") as mock_image:
        mock_image_instance = MagicMock()
        mock_image.return_value = mock_image_instance

        result = tools["get_canvas_preview"](session_id="s1")

        assert result is mock_image_instance


def test_get_pixel_color_returns_parsed_json(setup):
    """测试 get_pixel_color 解析 Lua 脚本返回的 JSON。"""
    tools, session_manager, runner = setup
    runner.run_script.return_value = {
        "success": True,
        "stdout": '{"x": 5, "y": 10, "hex": "#FF0000", "r": 255, "g": 0, "b": 0, "a": 255}',
        "stderr": "",
    }

    result = tools["get_pixel_color"](session_id="s1", x=5, y=10)

    assert result["hex"] == "#FF0000"
    assert result["r"] == 255
    assert result["g"] == 0
    assert result["b"] == 0


def test_get_pixel_color_handles_error(setup):
    """测试 get_pixel_color 处理错误响应。"""
    tools, session_manager, runner = setup
    runner.run_script.return_value = {
        "success": True,
        "stdout": '{"error": "coordinates out of bounds"}',
        "stderr": "",
    }

    result = tools["get_pixel_color"](session_id="s1", x=100, y=100)

    assert result["success"] is False
    assert "out of bounds" in result["error"]
