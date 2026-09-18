"""端到端测试：使用真实 Aseprite 验证完整流程。

运行方式：pytest -m e2e
前置条件：Aseprite 已安装在默认路径或通过 ASEPRITE_PATH 环境变量配置。
"""

import os
import json
from pathlib import Path

import pytest

from src.config import Config
from src.session import SessionManager
from src.runner import AsepriteRunner


# 跳过条件：Aseprite 不存在时跳过
ASEPRITE_PATH = os.environ.get(
    "ASEPRITE_PATH",
    r"D:\cxdownload\game_develop\Aseprite-v1.3.17.2-Source\build\bin\aseprite.exe",
)
skip_if_no_aseprite = pytest.mark.skipif(
    not Path(ASEPRITE_PATH).exists(),
    reason=f"Aseprite not found at {ASEPRITE_PATH}",
)


@pytest.fixture
def e2e_setup(tmp_path, monkeypatch):
    """端到端测试 fixture：真实 Aseprite + 临时工作目录。"""
    monkeypatch.setenv("ASEPRITE_WORK_DIR", str(tmp_path / "work"))
    config = Config()
    config.work_dir = tmp_path / "work"
    config.work_dir.mkdir()

    session_manager = SessionManager(config)
    runner = AsepriteRunner(config)

    # 验证 Aseprite 可执行
    if not runner.check_aseprite_exists():
        pytest.skip(f"Aseprite not found at {config.aseprite_path}")

    return session_manager, runner


@skip_if_no_aseprite
@pytest.mark.e2e
def test_e2e_create_and_export(e2e_setup):
    """端到端测试：创建画布 → 画像素 → 导出 PNG。"""
    session_manager, runner = e2e_setup

    # 1. 创建会话
    session_id = session_manager.create_session(width=16, height=16)
    ase_path = session_manager.get_ase_path(session_id)

    # 2. 执行 create_sprite.lua
    result = runner.run_script("create_sprite.lua", {
        "width": "16", "height": "16",
        "color_mode": "rgb", "file": str(ase_path),
    })
    assert result["success"], f"Failed to create sprite: {result.get('stderr')}"

    # 3. 画一个红色像素
    result = runner.run_script("draw_pixel.lua", {
        "file": str(ase_path), "x": "5", "y": "5", "color": "#FF0000",
    })
    assert result["success"], f"Failed to draw pixel: {result.get('stderr')}"

    # 4. 导出 PNG
    png_path = session_manager.get_work_dir(session_id) / "preview.png"
    result = runner.run_script("export_png.lua", {
        "file": str(ase_path), "output": str(png_path), "scale": "1",
    })
    assert result["success"], f"Failed to export PNG: {result.get('stderr')}"

    # 5. 验证 PNG 文件存在且非空
    assert png_path.exists(), "PNG file was not created"
    assert png_path.stat().st_size > 0, "PNG file is empty"


@skip_if_no_aseprite
@pytest.mark.e2e
def test_e2e_get_pixel_color(e2e_setup):
    """端到端测试：画像素后查询颜色。"""
    session_manager, runner = e2e_setup

    session_id = session_manager.create_session(width=16, height=16)
    ase_path = session_manager.get_ase_path(session_id)

    # 创建画布
    runner.run_script("create_sprite.lua", {
        "width": "16", "height": "16",
        "color_mode": "rgb", "file": str(ase_path),
    })

    # 画红色像素
    runner.run_script("draw_pixel.lua", {
        "file": str(ase_path), "x": "10", "y": "10", "color": "#FF0000",
    })

    # 查询像素颜色
    result = runner.run_script("get_pixel_color.lua", {
        "file": str(ase_path), "x": "10", "y": "10",
    })
    assert result["success"]

    data = json.loads(result["stdout"].strip())
    assert data["hex"] == "#FF0000"
    assert data["r"] == 255
    assert data["g"] == 0
    assert data["b"] == 0


@skip_if_no_aseprite
@pytest.mark.e2e
def test_e2e_draw_rect_and_export(e2e_setup):
    """端到端测试：画矩形并导出。"""
    session_manager, runner = e2e_setup

    session_id = session_manager.create_session(width=32, height=32)
    ase_path = session_manager.get_ase_path(session_id)

    # 创建画布
    runner.run_script("create_sprite.lua", {
        "width": "32", "height": "32",
        "color_mode": "rgb", "file": str(ase_path),
    })

    # 画实心矩形
    result = runner.run_script("draw_rect.lua", {
        "file": str(ase_path), "x": "0", "y": "0",
        "width": "10", "height": "10",
        "color": "#00FF00", "filled": "true",
    })
    assert result["success"]

    # 导出 PNG（2 倍缩放）
    png_path = session_manager.get_work_dir(session_id) / "preview.png"
    result = runner.run_script("export_png.lua", {
        "file": str(ase_path), "output": str(png_path), "scale": "2",
    })
    assert result["success"]
    assert png_path.exists()


@skip_if_no_aseprite
@pytest.mark.e2e
def test_e2e_full_iteration_workflow(e2e_setup):
    """端到端测试：完整迭代工作流（创建→绘制→预览→清除→重绘→保存）。"""
    session_manager, runner = e2e_setup

    # 1. 创建画布
    session_id = session_manager.create_session(width=16, height=16)
    ase_path = session_manager.get_ase_path(session_id)

    runner.run_script("create_sprite.lua", {
        "width": "16", "height": "16",
        "color_mode": "rgb", "file": str(ase_path),
    })

    # 2. 画一个线
    runner.run_script("draw_line.lua", {
        "file": str(ase_path),
        "x1": "0", "y1": "0", "x2": "15", "y2": "15",
        "color": "#0000FF",
    })

    # 3. 导出预览
    png_path = session_manager.get_work_dir(session_id) / "preview.png"
    result = runner.run_script("export_png.lua", {
        "file": str(ase_path), "output": str(png_path), "scale": "4",
    })
    assert result["success"]
    assert png_path.exists()

    # 4. 清除区域
    runner.run_script("clear_region.lua", {
        "file": str(ase_path), "x": "0", "y": "0",
        "width": "5", "height": "5",
    })

    # 5. 验证清除后像素变为透明
    result = runner.run_script("get_pixel_color.lua", {
        "file": str(ase_path), "x": "2", "y": "2",
    })
    data = json.loads(result["stdout"].strip())
    assert data["a"] == 0, "Pixel should be transparent after clear"

    # 6. 保存最终结果
    output_path = session_manager.get_work_dir(session_id) / "final.png"
    result = runner.run_script("save_sprite.lua", {
        "file": str(ase_path), "output": str(output_path),
    })
    assert result["success"]
    assert output_path.exists()
