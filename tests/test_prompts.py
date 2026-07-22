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
