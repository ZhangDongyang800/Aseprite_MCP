"""AsepriteRunner 测试。"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.config import Config
from src.runner import AsepriteRunner


@pytest.fixture
def runner():
    """使用 mock 配置的 AsepriteRunner。"""
    config = Config()
    config.aseprite_path = "/fake/aseprite.exe"
    config.scripts_dir = Path("/fake/scripts")
    return AsepriteRunner(config)


def test_run_script_builds_correct_command(runner):
    """测试 run_script 构造正确的命令行。"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="OK\n", stderr=""
        )

        result = runner.run_script("draw_pixel.lua", {
            "file": "/path/to/canvas.ase",
            "x": "10",
            "y": "20",
            "color": "#FF0000",
        })

        # 验证 subprocess.run 被调用
        mock_run.assert_called_once()

        # 获取实际调用的参数
        call_args = mock_run.call_args
        cmd = call_args[0][0]  # 第一个位置参数是命令列表

        # 验证命令包含 aseprite 路径
        assert cmd[0] == "/fake/aseprite.exe"
        # 验证 -b 标志
        assert "-b" in cmd
        # 验证 --script 参数
        script_idx = cmd.index("--script")
        assert cmd[script_idx + 1] == str(Path("/fake/scripts/draw_pixel.lua"))
        # 验证 --script-param 参数
        assert "--script-param" in cmd


def test_run_script_returns_success_dict(runner):
    """测试成功时返回正确的字典。"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="OK: drew pixel\n", stderr=""
        )

        result = runner.run_script("draw_pixel.lua", {"file": "test.ase"})

        assert result["success"] is True
        assert result["stdout"] == "OK: drew pixel\n"
        assert result["stderr"] == ""


def test_run_script_returns_failure_dict(runner):
    """测试失败时返回正确的字典。"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="ERROR: file not found\n"
        )

        result = runner.run_script("draw_pixel.lua", {"file": "missing.ase"})

        assert result["success"] is False
        assert result["stdout"] == ""
        assert "ERROR: file not found" in result["stderr"]


def test_run_script_passes_all_params(runner):
    """测试所有参数都通过 --script-param 传递。"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="OK", stderr=""
        )

        runner.run_script("draw_rect.lua", {
            "file": "canvas.ase",
            "x": "0",
            "y": "0",
            "width": "10",
            "height": "10",
            "color": "#00FF00",
        })

        cmd = mock_run.call_args[0][0]

        # 应该有 6 个 --script-param（每个参数一个）
        param_count = cmd.count("--script-param")
        assert param_count == 6

        # 验证具体参数值
        for key, value in [
            ("file", "canvas.ase"),
            ("x", "0"),
            ("y", "0"),
            ("width", "10"),
            ("height", "10"),
            ("color", "#00FF00"),
        ]:
            assert f"{key}={value}" in cmd


def test_run_script_timeout(runner):
    """测试超时处理。"""
    import subprocess

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="aseprite", timeout=30
        )

        result = runner.run_script("slow_script.lua", {})

        assert result["success"] is False
        assert "timeout" in result["error"].lower()


def test_run_script_file_not_found(runner):
    """测试 Aseprite 可执行文件不存在。"""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("aseprite not found")

        result = runner.run_script("draw_pixel.lua", {"file": "test.ase"})

        assert result["success"] is False
        assert "not found" in result["error"].lower()


def test_check_aseprite_exists_true(runner):
    """测试检查 Aseprite 存在（mock Path.exists）。"""
    with patch("pathlib.Path.exists", return_value=True):
        assert runner.check_aseprite_exists() is True


def test_check_aseprite_exists_false(runner):
    """测试检查 Aseprite 不存在。"""
    with patch("pathlib.Path.exists", return_value=False):
        assert runner.check_aseprite_exists() is False
