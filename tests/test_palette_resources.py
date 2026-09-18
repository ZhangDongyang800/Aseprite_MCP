"""调色板预设 Resources 测试（Task 1）。"""

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


def test_list_palette_presets(setup):
    """测试 list_palette_presets 返回预设名称列表。"""
    resources, _ = setup

    result = resources["aseprite://palette/presets"]()

    data = json.loads(result)
    assert "presets" in data
    presets = data["presets"]
    # 五个公开标准预设
    assert "db16" in presets
    assert "db32" in presets
    assert "aap64" in presets
    assert "nes" in presets
    assert "gameboy" in presets
    assert len(presets) == 5


def test_get_palette_preset_known(setup):
    """测试获取已存在的预设调色板（db16）。"""
    resources, _ = setup

    result = resources["aseprite://palette/presets/{name}"]("db16")

    data = json.loads(result)
    assert data["name"] == "db16"
    assert "description" in data
    assert isinstance(data["colors"], list)
    assert len(data["colors"]) == 16
    # 校验色值格式
    assert all(c.startswith("#") and len(c) == 7 for c in data["colors"])


def test_get_palette_preset_db32(setup):
    """测试 db32 预设包含 32 色。"""
    resources, _ = setup

    result = resources["aseprite://palette/presets/{name}"]("db32")

    data = json.loads(result)
    assert data["name"] == "db32"
    assert len(data["colors"]) == 32


def test_get_palette_preset_aap64(setup):
    """测试 aap64 预设返回完整 64 色标准色值列表。

    色值来源：lospec.com/palette-list/aap-64（Adigun Polack 设计的 64 色标准）。
    """
    resources, _ = setup

    result = resources["aseprite://palette/presets/{name}"]("aap64")

    data = json.loads(result)
    assert data["name"] == "aap64"
    # AAP-64 标准为 64 色
    assert len(data["colors"]) == 64
    # 校验色值格式
    assert all(c.startswith("#") and len(c) == 7 for c in data["colors"])


def test_get_palette_preset_gameboy(setup):
    """测试 gameboy 预设包含 4 色。"""
    resources, _ = setup

    result = resources["aseprite://palette/presets/{name}"]("gameboy")

    data = json.loads(result)
    assert data["name"] == "gameboy"
    assert len(data["colors"]) == 4


def test_get_palette_preset_not_found(setup):
    """测试获取不存在的预设返回 error。"""
    resources, _ = setup

    result = resources["aseprite://palette/presets/{name}"]("nonexistent")

    data = json.loads(result)
    assert "error" in data
    assert "nonexistent" in data["error"]
