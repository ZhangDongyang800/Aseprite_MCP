"""瓦片布局模板 Resources 测试（Task 7，docs §8.2/§8.3）。"""

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


def test_list_tileset_templates(setup):
    """测试 list_tileset_templates 返回所有瓦片模板摘要列表。"""
    resources, _ = setup

    result = resources["aseprite://tileset/templates"]()

    data = json.loads(result)
    assert "templates" in data
    templates = data["templates"]
    # docs §8.2 共 3 个瓦片模板
    expected = ["grass_dirt_16x16", "dungeon_16x16", "water_grass_16x16"]
    for name in expected:
        assert name in templates
        # 摘要应包含 description 和 tile_size，但不含 grid/colormap
        assert "description" in templates[name]
        assert "tile_size" in templates[name]
        assert "grid" not in templates[name]
        assert "colormap" not in templates[name]
    assert len(templates) == len(expected)


def test_get_tileset_template_grass_dirt(setup):
    """测试获取 grass_dirt_16x16 模板（草地+泥土，含中心/边缘块）。"""
    resources, _ = setup

    result = resources["aseprite://tileset/templates/{name}"]("grass_dirt_16x16")

    data = json.loads(result)
    assert data["name"] == "grass_dirt_16x16"
    assert data["tile_size"] == 16
    assert "description" in data
    assert "grid" in data
    assert "colormap" in data
    # 色值映射应包含 G（草地）与 D（泥土）
    assert "G=#4A7C20" in data["colormap"]
    assert "D=#8B5A2B" in data["colormap"]


def test_get_tileset_template_dungeon(setup):
    """测试获取 dungeon_16x16 模板（地牢石墙）。"""
    resources, _ = setup

    result = resources["aseprite://tileset/templates/{name}"]("dungeon_16x16")

    data = json.loads(result)
    assert data["name"] == "dungeon_16x16"
    assert data["tile_size"] == 16
    assert "grid" in data
    assert "colormap" in data
    # 石墙色 S=#5C5C5C
    assert "S=#5C5C5C" in data["colormap"]


def test_get_tileset_template_water_grass(setup):
    """测试获取 water_grass_16x16 模板（水面+草地过渡）。"""
    resources, _ = setup

    result = resources["aseprite://tileset/templates/{name}"]("water_grass_16x16")

    data = json.loads(result)
    assert data["name"] == "water_grass_16x16"
    assert data["tile_size"] == 16
    assert "grid" in data
    assert "colormap" in data
    # 水 W=#2980B9，草 G=#4A7C20
    assert "W=#2980B9" in data["colormap"]
    assert "G=#4A7C20" in data["colormap"]


def test_get_tileset_template_grid_dimensions(setup):
    """测试所有模板的 grid 行数为 16（16x16 瓦片）。"""
    resources, _ = setup

    for name in ["grass_dirt_16x16", "dungeon_16x16", "water_grass_16x16"]:
        data = json.loads(resources["aseprite://tileset/templates/{name}"](name))
        # grid 使用 / 分隔行
        rows = data["grid"].split("/")
        assert len(rows) == 16, f"{name} 应有 16 行"
        # 每行宽度为 16
        for row in rows:
            assert len(row) == 16, f"{name} 每行应为 16 字符"


def test_get_tileset_template_not_found(setup):
    """测试获取不存在的瓦片模板返回 error。"""
    resources, _ = setup

    result = resources["aseprite://tileset/templates/{name}"]("nonexistent")

    data = json.loads(result)
    assert "error" in data
    assert "nonexistent" in data["error"]
