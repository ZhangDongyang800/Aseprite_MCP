"""调色板增强工具测试：apply_preset_palette / append_palette_colors / derive_shading_palette。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.palette_tools import register_palette_tools


@pytest.fixture
def setup():
    """mock 依赖并捕获工具函数。"""
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
    register_palette_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_apply_preset_palette_calls_apply_palette_script(setup):
    """apply_preset_palette 应调用 apply_palette.lua 并传入预设色值。"""
    tools, session_manager, runner = setup
    runner.run_script.return_value = {
        "success": True, "stdout": "OK", "stderr": ""
    }

    result = tools["apply_preset_palette"](session_id="s1", preset_name="gameboy")

    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "apply_palette.lua"
    # gameboy 4 色，应包含 #0F380F
    assert "#0F380F" in call_args[0][1]["colors"]


def test_apply_preset_palette_rejects_unknown_preset(setup):
    """未知预设名应返回错误。"""
    tools, _, _ = setup
    result = tools["apply_preset_palette"](session_id="s1", preset_name="unknown")
    assert result["success"] is False
    assert "unknown" in result["error"]


def test_append_palette_colors_calls_append_script(setup):
    """append_palette_colors 应调用 append_palette.lua。"""
    tools, _, runner = setup
    result = tools["append_palette_colors"](
        session_id="s1", colors="#FF0000,#00FF00,#0000FF"
    )
    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "append_palette.lua"
    assert call_args[0][1]["colors"] == "#FF0000,#00FF00,#0000FF"


def test_derive_shading_palette_returns_five_shades(setup):
    """derive_shading_palette 默认返回 5 阶配色。"""
    tools, _, _ = setup
    result = tools["derive_shading_palette"](base_color="#808080", apply_to_palette=False)
    assert result["success"] is True
    assert len(result["colors_hex"]) == 5
    assert result["colors_hex"][4] == "#000000"  # outline（index 4，从亮到暗最后一位）


def test_derive_shading_palette_highlight_is_brighter(setup):
    """高光色应比主色亮。"""
    tools, _, _ = setup
    result = tools["derive_shading_palette"](base_color="#808080", apply_to_palette=False)
    colors = result["colors_hex"]
    # colors[0]=highlight, colors[1]=base
    assert int(colors[0][1:3], 16) > int(colors[1][1:3], 16)


def test_derive_shading_palette_hue_shift_off(setup):
    """hue_shift=false 时关闭色相偏移（纯亮度缩放）。"""
    tools, _, _ = setup
    result = tools["derive_shading_palette"](
        base_color="#808080", hue_shift=False, apply_to_palette=False
    )
    # 关闭色相偏移后，灰色的高光三通道应相等
    hl = result["colors_hex"][0]
    r, g, b = int(hl[1:3], 16), int(hl[3:5], 16), int(hl[5:7], 16)
    assert r == g == b


def test_derive_shading_palette_apply_calls_append(setup):
    """apply_to_palette=true 时应调用 append_palette.lua 追加。"""
    tools, _, runner = setup
    result = tools["derive_shading_palette"](base_color="#808080", apply_to_palette=True, session_id="s1")
    assert result["success"] is True
    assert runner.run_script.called
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "append_palette.lua"
