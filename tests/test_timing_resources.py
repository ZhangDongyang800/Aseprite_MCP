"""帧时长预设 Resources 测试（Task 4，docs §7.2）。"""

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


def test_list_timing_presets(setup):
    """测试 list_timing_presets 返回所有动画类型预设名称列表。"""
    resources, _ = setup

    result = resources["aseprite://timing/presets"]()

    data = json.loads(result)
    assert "presets" in data
    presets = data["presets"]
    # docs §7.2 共 9 个动画类型预设
    expected = [
        "idle", "walk", "run",
        "attack_windup", "attack_hit", "attack_recover",
        "jump_start", "jump_apex", "jump_land",
    ]
    for name in expected:
        assert name in presets
    assert len(presets) == len(expected)


def test_get_timing_preset_walk(setup):
    """测试获取 walk 行走循环预设。"""
    resources, _ = setup

    result = resources["aseprite://timing/presets/{type}"]("walk")

    data = json.loads(result)
    assert data["type"] == "walk"
    assert data["description"] == "行走循环"
    assert data["frame_count_range"] == [4, 6]
    assert data["duration_ms"] == 125


def test_get_timing_preset_idle(setup):
    """测试获取 idle 待机呼吸预设。"""
    resources, _ = setup

    result = resources["aseprite://timing/presets/{type}"]("idle")

    data = json.loads(result)
    assert data["type"] == "idle"
    assert data["duration_ms"] == 400
    assert data["frame_count_range"] == [2, 4]


def test_get_timing_preset_run(setup):
    """测试获取 run 跑步循环预设。"""
    resources, _ = setup

    result = resources["aseprite://timing/presets/{type}"]("run")

    data = json.loads(result)
    assert data["type"] == "run"
    assert data["duration_ms"] == 80
    assert data["frame_count_range"] == [6, 8]


def test_get_timing_preset_attack_phases(setup):
    """测试攻击三阶段预设（蓄力/命中/恢复）时长差异。"""
    resources, _ = setup

    windup = json.loads(resources["aseprite://timing/presets/{type}"]("attack_windup"))
    hit = json.loads(resources["aseprite://timing/presets/{type}"]("attack_hit"))
    recover = json.loads(resources["aseprite://timing/presets/{type}"]("attack_recover"))

    # 命中帧应保持更长（docs §7.2）
    assert hit["duration_ms"] > windup["duration_ms"]
    assert hit["duration_ms"] > recover["duration_ms"]
    assert windup["type"] == "attack_windup"
    assert hit["type"] == "attack_hit"
    assert recover["type"] == "attack_recover"


def test_get_timing_preset_jump_phases(setup):
    """测试跳跃三阶段预设。"""
    resources, _ = setup

    start = json.loads(resources["aseprite://timing/presets/{type}"]("jump_start"))
    apex = json.loads(resources["aseprite://timing/presets/{type}"]("jump_apex"))
    land = json.loads(resources["aseprite://timing/presets/{type}"]("jump_land"))

    # 顶点保持时间最长
    assert apex["duration_ms"] == 150
    assert start["frame_count_range"] == [1, 2]
    # jump_apex 只有 1 帧
    assert apex["frame_count_range"] == [1, 1]
    assert land["type"] == "jump_land"


def test_get_timing_preset_not_found(setup):
    """测试获取不存在的动画类型返回 error。"""
    resources, _ = setup

    result = resources["aseprite://timing/presets/{type}"]("nonexistent")

    data = json.loads(result)
    assert "error" in data
    assert "nonexistent" in data["error"]
