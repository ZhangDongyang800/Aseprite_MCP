"""规范检查规则 Resources 测试（Task 10，docs §2/§4/§5/§7）。"""

import json
import pytest
from unittest.mock import MagicMock

from src.resources import register_resources


@pytest.fixture
def setup():
    """提供 mock 依赖，并捕获注册的 resource 函数。"""
    session_manager = MagicMock()
    session_manager.list_sessions.return_value = []
    session_manager.get_canvas_info.return_value = {
        "width": 16, "height": 16, "color_mode": "rgb"
    }

    resources = {}
    mcp = MagicMock()

    def capture_resource(uri=None, **kwargs):
        def decorator(func):
            resources[uri or func.__name__] = func
            return func
        return decorator

    mcp.resource = capture_resource

    register_resources(mcp, session_manager)
    return resources, session_manager


def test_get_standards_size(setup):
    """测试获取 size 尺寸规范（docs §2.1）。"""
    resources, _ = setup

    result = resources["aseprite://standards/{category}"]("size")

    data = json.loads(result)
    assert data["category"] == "size"
    # 尺寸应为 8/16/32/64
    assert data["allowed"] == [8, 16, 32, 64]
    assert data["modulo"] == 8
    assert "rules" in data


def test_get_standards_palette(setup):
    """测试获取 palette 调色板规范（docs §4.1/§4.2）。"""
    resources, _ = setup

    result = resources["aseprite://standards/{category}"]("palette")

    data = json.loads(result)
    assert data["category"] == "palette"
    # 颜色数建议 4-32
    assert data["min_colors"] == 4
    assert data["max_colors"] == 32
    assert "rules" in data


def test_get_standards_timing(setup):
    """测试获取 timing 动画时长规范（docs §7.2）。"""
    resources, _ = setup

    result = resources["aseprite://standards/{category}"]("timing")

    data = json.loads(result)
    assert data["category"] == "timing"
    assert "rules" in data


def test_get_standards_pixel_art(setup):
    """测试获取 pixel_art 像素艺术规范（docs §5）。"""
    resources, _ = setup

    result = resources["aseprite://standards/{category}"]("pixel_art")

    data = json.loads(result)
    assert data["category"] == "pixel_art"
    # 机器可检查项：半透明像素、孤立像素
    assert "semi_transparent" in data["machine_checkable"]
    assert "isolated_pixels" in data["machine_checkable"]
    # 视觉审查项：锯齿、枕头阴影
    assert "jaggies_shape" in data["visual_review"]
    assert "pillow_shading" in data["visual_review"]
    assert "rules" in data


def test_get_standards_all_categories(setup):
    """测试所有 4 个类别均可访问（docs §2/§4/§5/§7）。"""
    resources, _ = setup

    expected = ["size", "palette", "timing", "pixel_art"]
    for category in expected:
        data = json.loads(
            resources["aseprite://standards/{category}"](category)
        )
        assert data["category"] == category
        assert "rules" in data


def test_get_standards_not_found(setup):
    """测试获取不存在的规范类别返回 error。"""
    resources, _ = setup

    result = resources["aseprite://standards/{category}"]("nonexistent")

    data = json.loads(result)
    assert "error" in data
    assert "nonexistent" in data["error"]
