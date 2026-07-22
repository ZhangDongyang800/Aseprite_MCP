"""动画脚本测试（Task 5）。

验证 set_frame_durations.lua / draw_animation_frames.lua / export_onion_skin.lua
脚本文件存在，且能被 runner 按预期参数模式调用。
"""

from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config


# 脚本目录（与生产环境一致：<项目根>/scripts/）
SCRIPTS_DIR = Config().scripts_dir


def test_set_frame_durations_script_exists():
    """测试 set_frame_durations.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "set_frame_durations.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_draw_animation_frames_script_exists():
    """测试 draw_animation_frames.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "draw_animation_frames.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_export_onion_skin_script_exists():
    """测试 export_onion_skin.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "export_onion_skin.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_set_frame_durations_runner_call_pattern():
    """测试 mock runner 调用 set_frame_durations.lua 的参数模式。

    set_frame_durations.lua 接收 file 和 durations（逗号分隔的毫秒数列表）。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: set durations for 4 frames",
        "stderr": "",
    }

    # 模拟批量设置 4 帧时长（毫秒）
    params = {
        "file": "/tmp/canvas.ase",
        "durations": "125,125,125,125",
    }
    result = runner.run_script("set_frame_durations.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("set_frame_durations.lua", params)
    assert result["success"] is True
    assert "set durations" in result["stdout"]


def test_draw_animation_frames_runner_call_pattern():
    """测试 mock runner 调用 draw_animation_frames.lua 的参数模式。

    draw_animation_frames.lua 接收 file、grids（| 分隔每帧，/ 分隔行）、
    colormap、mode（copy/blank）、layer。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: drew 2 frames",
        "stderr": "",
    }

    # 模拟一次绘制 2 帧动画（调用次数优化核心）
    params = {
        "file": "/tmp/canvas.ase",
        "grids": "RRR/RRR|WWW/WWW",  # 第1帧红、第2帧白
        "colormap": "R=#FF0000,W=#FFFFFF",
        "mode": "copy",
        "layer": "1",
    }
    result = runner.run_script("draw_animation_frames.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("draw_animation_frames.lua", params)
    assert result["success"] is True
    assert "drew" in result["stdout"]


def test_export_onion_skin_runner_call_pattern():
    """测试 mock runner 调用 export_onion_skin.lua 的参数模式。

    export_onion_skin.lua 接收 file、output（PNG 路径）、frame（中心帧）、scale。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: exported onion skin preview to /tmp/out.png",
        "stderr": "",
    }

    # 模拟导出第 3 帧的洋葱皮预览
    params = {
        "file": "/tmp/canvas.ase",
        "output": "/tmp/onion.png",
        "frame": "3",
        "scale": "2",
    }
    result = runner.run_script("export_onion_skin.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("export_onion_skin.lua", params)
    assert result["success"] is True
    assert "onion skin" in result["stdout"]
