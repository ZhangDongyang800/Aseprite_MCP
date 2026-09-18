"""MCP Prompts 测试。"""

import pytest
from unittest.mock import MagicMock

from src.prompts import register_prompts


@pytest.fixture
def setup():
    """提供 mock mcp。"""
    prompts = {}
    mcp = MagicMock()

    def capture_prompt(func=None, **kwargs):
        if func is None:
            return lambda f: capture_prompt(f, **kwargs)
        prompts[func.__name__] = func
        return func

    mcp.prompt = capture_prompt

    register_prompts(mcp)
    return prompts


def test_create_sprite_prompt_contains_description(setup):
    """测试创作引导 prompt 包含描述。"""
    prompts = setup

    result = prompts["create_sprite_prompt"](
        description="一个红色的蘑菇", size="16x16"
    )

    assert "一个红色的蘑菇" in result
    assert "16x16" in result


def test_create_sprite_prompt_contains_workflow(setup):
    """测试创作引导 prompt 包含工作流程说明。"""
    prompts = setup

    result = prompts["create_sprite_prompt"](
        description="测试", size="32x32"
    )

    assert "create_sprite" in result
    assert "get_canvas_preview" in result
    assert "save_sprite" in result


def test_create_sprite_prompt_default_size(setup):
    """测试默认尺寸为 16x16。"""
    prompts = setup

    result = prompts["create_sprite_prompt"](description="测试")

    assert "16x16" in result


def test_iterate_sprite_prompt_contains_feedback(setup):
    """测试迭代引导 prompt 包含反馈信息。"""
    prompts = setup

    result = prompts["iterate_sprite_prompt"](
        session_id="s1", feedback="圆形不够圆，左侧像素偏了"
    )

    assert "s1" in result
    assert "圆形不够圆" in result


def test_iterate_sprite_prompt_contains_tools(setup):
    """测试迭代引导 prompt 包含工具使用说明。"""
    prompts = setup

    result = prompts["iterate_sprite_prompt"](
        session_id="s1", feedback="测试反馈"
    )

    assert "get_canvas_preview" in result
    assert "clear_region" in result


# ══════════════════════════════════════════
# create_tileset_prompt 测试（Task 15）
# ══════════════════════════════════════════

def test_create_tileset_prompt_registered(setup):
    """测试 create_tileset_prompt 已注册。"""
    prompts = setup
    assert "create_tileset_prompt" in prompts


def test_create_tileset_prompt_contains_description(setup):
    """测试瓦片集 prompt 包含描述。"""
    prompts = setup

    result = prompts["create_tileset_prompt"](
        description="草地与泥土过渡瓦片", tile_size="16x16", cols=6, rows=3
    )

    assert "草地与泥土过渡瓦片" in result
    assert "16x16" in result
    assert "6x3" in result


def test_create_tileset_prompt_contains_workflow(setup):
    """测试瓦片集 prompt 包含 Tileset 工作流工具。"""
    prompts = setup

    result = prompts["create_tileset_prompt"](description="测试瓦片")

    # 关键工具必须出现
    assert "create_tileset_canvas" in result
    assert "draw_from_grid" in result
    assert "export_tiled_preview" in result
    assert "save_sprite" in result


def test_create_tileset_prompt_contains_call_baseline(setup):
    """测试瓦片集 prompt 包含调用基准（理想调用次数）。"""
    prompts = setup

    result = prompts["create_tileset_prompt"](description="测试瓦片")

    assert "理想调用次数" in result
    # 禁止逐像素绘制瓦片
    assert "禁止" in result


def test_create_tileset_prompt_default_params(setup):
    """测试瓦片集 prompt 默认参数。"""
    prompts = setup

    result = prompts["create_tileset_prompt"](description="默认瓦片")

    # 默认 tile_size=16x16, cols=6, rows=3
    assert "16x16" in result
    assert "6x3" in result
    # 默认 tile_size.split('x')[0] = "16"
    assert "tile_size=16" in result


# ══════════════════════════════════════════
# create_animation_prompt 调用基准测试（Task 15）
# ══════════════════════════════════════════

def test_create_animation_prompt_contains_call_baseline(setup):
    """测试动画 prompt 包含调用基准（理想调用次数）。"""
    prompts = setup

    result = prompts["create_animation_prompt"](
        description="行走循环", frame_count=4, fps=8
    )

    # 调用基准段落
    assert "理想调用次数" in result
    # 批量工具优先
    assert "draw_animation_frames" in result
    assert "apply_timing_preset" in result
    # 禁止逐帧循环
    assert "禁止" in result
