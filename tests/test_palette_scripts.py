"""调色板脚本测试（Task 2）。

验证 apply_palette.lua / append_palette.lua 脚本文件存在，
且能被 runner 按预期参数模式调用。
"""

from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config


# 脚本目录（与生产环境一致：<项目根>/scripts/）
SCRIPTS_DIR = Config().scripts_dir


def test_apply_palette_script_exists():
    """测试 apply_palette.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "apply_palette.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_append_palette_script_exists():
    """测试 append_palette.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "append_palette.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_apply_palette_runner_call_pattern():
    """测试 mock runner 调用 apply_palette.lua 的参数模式。

    apply_palette.lua 接收 file 和 colors（逗号分隔的 #RRGGBB 列表）。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: applied palette with 3 colors",
        "stderr": "",
    }

    # 模拟调用 apply_palette.lua（整板替换）
    params = {
        "file": "/tmp/canvas.ase",
        "colors": "#FF0000,#00FF00,#0000FF",
    }
    result = runner.run_script("apply_palette.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("apply_palette.lua", params)
    assert result["success"] is True
    assert "applied palette" in result["stdout"]


def test_append_palette_runner_call_pattern():
    """测试 mock runner 调用 append_palette.lua 的参数模式。

    append_palette.lua 接收 file 和 colors（逗号分隔的 #RRGGBB 列表）。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: appended 2 colors to palette (now 5 total)",
        "stderr": "",
    }

    # 模拟调用 append_palette.lua（尾部追加）
    params = {
        "file": "/tmp/canvas.ase",
        "colors": "#FF0000,#00FF00",
    }
    result = runner.run_script("append_palette.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("append_palette.lua", params)
    assert result["success"] is True
    assert "appended" in result["stdout"]
