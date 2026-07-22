"""MCP Resources 测试。"""

import json
import pytest
from unittest.mock import MagicMock

from src.resources import register_resources


@pytest.fixture
def setup():
    """提供 mock 依赖。"""
    session_manager = MagicMock()
    session_manager.list_sessions.return_value = [
        {"session_id": "s1", "width": 16, "height": 16, "color_mode": "rgb"},
        {"session_id": "s2", "width": 32, "height": 32, "color_mode": "rgb"},
    ]
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


def test_list_sessions_resource(setup):
    """测试会话列表 resource 返回 JSON。"""
    resources, session_manager = setup

    result = resources["aseprite://sessions"]()

    data = json.loads(result)
    assert len(data) == 2
    assert data[0]["session_id"] == "s1"
    assert data[1]["session_id"] == "s2"


def test_get_canvas_info_resource(setup):
    """测试画布信息 resource 返回 JSON。"""
    resources, session_manager = setup

    result = resources["aseprite://canvas/{session_id}/info"]("s1")

    data = json.loads(result)
    assert data["width"] == 16
    assert data["height"] == 16
    assert data["color_mode"] == "rgb"


def test_get_default_palette_resource(setup):
    """测试默认调色板 resource 返回 JSON。"""
    resources, session_manager = setup

    result = resources["aseprite://palette/default"]()

    data = json.loads(result)
    assert "colors" in data
    assert isinstance(data["colors"], list)
    assert len(data["colors"]) > 0
