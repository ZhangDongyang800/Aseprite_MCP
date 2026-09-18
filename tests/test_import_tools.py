"""混合管线工具测试：cleanup_import_image。"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.tools.import_tools import register_import_tools
from PIL import Image as PILImage


@pytest.fixture
def setup(tmp_path):
    """提供 mock 依赖与一张合法输入 PNG。"""
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = tmp_path
    runner.run_script.return_value = {
        "success": True,
        "stdout": '{"ok": "stamped png onto layer 1 frame 1 at (0,0)"}',
        "stderr": "",
    }

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool

    register_import_tools(mcp, session_manager, runner)

    # 构造输入 PNG（非完美整数放大图，避免自动降采样误判）
    src = tmp_path / "input.png"
    img = PILImage.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(4, 6):
        for x in range(4, 6):
            img.putpixel((x, y), (255, 0, 0, 255))
    img.putpixel((10, 10), (0, 0, 255, 255))
    img.save(src)

    return tools, session_manager, runner, tmp_path, src


def test_cleanup_import_image_end_to_end(setup):
    """测试清洗 + 导入 + 返回预览图的完整流程。"""
    tools, session_manager, runner, tmp_path, src = setup

    result = tools["cleanup_import_image"](
        session_id="s1",
        image_path=str(src),
        max_colors=16,
        palette="",
        strip_background=True,
        scale=0,
        layer=1,
        frame=1,
        offset_x=0,
        offset_y=0,
    )

    # 返回 Image 指向清洗结果
    assert str(result.path).endswith("cleaned.png")
    assert (tmp_path / "cleaned.png").exists()

    # 导入调用 import_png.lua（stamp 模式，带 file 注入）
    runner.run_script.assert_called_once()
    script_name, params = runner.run_script.call_args[0]
    assert script_name == "import_png.lua"
    assert params["png_path"] == str(tmp_path / "cleaned.png")
    assert params["mode"] == "stamp"
    assert params["file"] == str(Path("/tmp/canvas.ase"))


def test_cleanup_import_image_with_palette(setup):
    """测试调色板锁定路径。"""
    tools, _, _, tmp_path, src = setup

    result = tools["cleanup_import_image"](
        session_id="s1",
        image_path=str(src),
        max_colors=8,
        palette="#FF0000,#0000FF",
    )

    assert str(result.path).endswith("cleaned.png")
    # 红色块像素被锁定到 #FF0000
    img = PILImage.open(tmp_path / "cleaned.png").convert("RGBA")
    assert img.getpixel((4, 4)) == (255, 0, 0, 255)


def test_cleanup_import_image_missing_file(setup):
    """测试输入文件不存在时抛错。"""
    tools, _, _, tmp_path, _ = setup

    with pytest.raises(RuntimeError, match="not found"):
        tools["cleanup_import_image"](
            session_id="s1",
            image_path=str(tmp_path / "nope.png"),
        )


def test_cleanup_import_image_invalid_palette(setup):
    """测试非法调色板抛错。"""
    tools, _, _, tmp_path, src = setup

    with pytest.raises(RuntimeError, match="Invalid palette"):
        tools["cleanup_import_image"](
            session_id="s1",
            image_path=str(src),
            palette="#ZZZZZZ",
        )


def test_cleanup_import_image_invalid_max_colors(setup):
    """测试非法 max_colors 抛 ValueError。"""
    tools, _, _, tmp_path, src = setup

    with pytest.raises(ValueError):
        tools["cleanup_import_image"](
            session_id="s1",
            image_path=str(src),
            max_colors=0,
        )
