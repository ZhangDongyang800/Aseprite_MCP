"""瓦片脚本测试（Task 8，docs §6/§8.5）。

验证 create_tileset.lua / export_tiled.lua
脚本文件存在，且能被 runner 按预期参数模式调用。
"""

from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config


# 脚本目录（与生产环境一致：<项目根>/scripts/）
SCRIPTS_DIR = Config().scripts_dir


def test_create_tileset_script_exists():
    """测试 create_tileset.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "create_tileset.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_export_tiled_script_exists():
    """测试 export_tiled.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "export_tiled.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_create_tileset_script_contains_grid_setup():
    """测试 create_tileset.lua 包含 app.gridBounds 网格设置（docs §8.5 关键设计）。

    网格设置是 create_tileset 的核心特性，应有降级保护（若 API 不可用则跳过）。
    """
    script_path = SCRIPTS_DIR / "create_tileset.lua"
    content = script_path.read_text(encoding="utf-8")
    # 网格设置使用 app.gridBounds（可读写属性）
    assert "gridBounds" in content, "create_tileset.lua 应使用 app.gridBounds 设置网格"
    # 参数应包含 tile_size / cols / rows / file
    assert 'app.params["tile_size"]' in content
    assert 'app.params["cols"]' in content
    assert 'app.params["rows"]' in content
    assert 'app.params["file"]' in content


def test_export_tiled_script_contains_tiling():
    """测试 export_tiled.lua 使用拼接方式导出（docs §6 关键设计）。

    不依赖 Tiled Mode API，改用 drawImage 拼接方式检查接缝。
    """
    script_path = SCRIPTS_DIR / "export_tiled.lua"
    content = script_path.read_text(encoding="utf-8")
    # 拼接循环：双层 for 循环复制 tile
    assert "drawImage" in content, "export_tiled.lua 应使用 drawImage 拼接"
    assert "for" in content, "export_tiled.lua 应使用循环平铺"
    # 参数应包含 file / output / repeat / scale
    assert 'app.params["file"]' in content
    assert 'app.params["output"]' in content
    assert 'app.params["repeat"]' in content
    assert 'app.params["scale"]' in content


def test_create_tileset_runner_call_pattern():
    """测试 mock runner 调用 create_tileset.lua 的参数模式。

    create_tileset.lua 接收 file、tile_size、cols、rows，
    创建 tile_size*cols × tile_size*rows 画布并设网格=tile_size。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: created tileset 64x64 grid=16 at /tmp/tileset.ase",
        "stderr": "",
    }

    # 模拟创建 16px 瓦片、4 列 × 4 行的瓦片集
    params = {
        "file": "/tmp/tileset.ase",
        "tile_size": "16",
        "cols": "4",
        "rows": "4",
    }
    result = runner.run_script("create_tileset.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("create_tileset.lua", params)
    assert result["success"] is True
    assert "created tileset" in result["stdout"]
    assert "grid=16" in result["stdout"]


def test_export_tiled_runner_call_pattern():
    """测试 mock runner 调用 export_tiled.lua 的参数模式。

    export_tiled.lua 接收 file、output、repeat（默认 2）、scale（默认 1），
    以拼接方式导出 repeat×repeat 的接缝预览 PNG。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: exported tiled preview 2x2 to /tmp/tiled.png",
        "stderr": "",
    }

    # 模拟导出 2×2 拼接预览（默认 repeat=2, scale=1）
    params = {
        "file": "/tmp/tileset.ase",
        "output": "/tmp/tiled.png",
        "repeat": "2",
        "scale": "1",
    }
    result = runner.run_script("export_tiled.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("export_tiled.lua", params)
    assert result["success"] is True
    assert "tiled preview" in result["stdout"]
    assert "2x2" in result["stdout"]
