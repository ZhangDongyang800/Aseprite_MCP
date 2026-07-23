"""精灵管理工具测试。"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from src.tools.sprite_tools import register_sprite_tools


@pytest.fixture
def setup():
    """提供 session_manager 和 mock runner。"""
    session_manager = MagicMock()
    runner = MagicMock()

    # 创建会话返回 fake session_id
    session_manager.create_session.return_value = "test-session-id"
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")

    # runner 成功执行
    runner.run_script.return_value = {
        "success": True, "stdout": "OK", "stderr": ""
    }

    # 收集注册的工具
    tools = {}
    mcp = MagicMock()

    # 捕获 @mcp.tool 装饰器注册的函数
    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool

    register_sprite_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_create_sprite_calls_session_and_runner(setup):
    """测试 create_sprite 创建会话并调用 Lua 脚本。"""
    tools, session_manager, runner = setup

    result = tools["create_sprite"](width=16, height=16, color_mode="rgb")

    # 验证创建了会话
    session_manager.create_session.assert_called_once_with(
        width=16, height=16, color_mode="rgb"
    )

    # 验证调用了 create_sprite.lua
    runner.run_script.assert_called_once()
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "create_sprite.lua"

    # 验证返回值包含 session_id
    assert result["session_id"] == "test-session-id"


def test_create_sprite_default_color_mode(setup):
    """测试默认颜色模式为 rgb。"""
    tools, session_manager, runner = setup

    tools["create_sprite"](width=32, height=32)

    session_manager.create_session.assert_called_once_with(
        width=32, height=32, color_mode="rgb"
    )


def test_open_sprite_calls_runner(setup):
    """测试 open_sprite 调用 Lua 脚本打开文件。"""
    tools, session_manager, runner = setup

    result = tools["open_sprite"](file_path="/path/to/existing.png")

    # 验证调用了 open_sprite.lua
    runner.run_script.assert_called_once()
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "open_sprite.lua"

    # 验证创建了会话
    session_manager.create_session.assert_called_once()


def test_save_sprite_calls_runner(setup):
    """测试 save_sprite 调用 Lua 脚本保存。"""
    tools, session_manager, runner = setup

    result = tools["save_sprite"](
        session_id="test-session-id", output_path="/output/result.png"
    )

    # 验证调用了 save_sprite.lua
    runner.run_script.assert_called_once()
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "save_sprite.lua"


def test_close_session_calls_session_manager(setup):
    """测试 close_session 调用 session_manager。"""
    tools, session_manager, runner = setup

    result = tools["close_session"](session_id="test-session-id")

    session_manager.close_session.assert_called_once_with("test-session-id")
    assert "closed" in result["status"].lower()


def test_create_sprite_handles_runner_failure(setup):
    """测试 runner 失败时返回错误。"""
    tools, session_manager, runner = setup
    runner.run_script.return_value = {
        "success": False, "stdout": "", "stderr": "ERROR: bad params", "error": "failed"
    }

    result = tools["create_sprite"](width=16, height=16)

    assert result["success"] is False
    assert "error" in result


# ===== import_png 工具测试 =====

def test_import_png_new_mode_creates_session_with_real_size(setup, tmp_path):
    """new 模式：从 PNG 创建会话，用真实尺寸刷新缓存。"""
    tools, session_manager, runner = setup
    # 创建真实 png 文件（内容无关，只需 exists 通过校验）
    png = tmp_path / "in.png"
    png.write_bytes(b"")
    # mock runner 返回尺寸 JSON（模拟 Lua 脚本输出）
    runner.run_script.return_value = {
        "success": True, "stdout": '{"width":20,"height":24}', "stderr": ""
    }

    result = tools["import_png"](png_path=str(png), mode="new")

    # 验证成功返回真实尺寸
    assert result["success"] is True
    assert result["width"] == 20
    assert result["height"] == 24
    # 验证调用了 import_png.lua
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "import_png.lua"
    assert call_args[0][1]["mode"] == "new"
    # 验证用真实尺寸刷新了会话缓存
    session_manager.update_canvas_info.assert_called_once()
    upd_args = session_manager.update_canvas_info.call_args[0]
    assert upd_args[1] == 20
    assert upd_args[2] == 24


def test_import_png_new_mode_parse_error_cleans_session(setup, tmp_path):
    """new 模式 Lua 输出非 JSON 时清理会话并报错。"""
    tools, session_manager, runner = setup
    png = tmp_path / "bad.png"
    png.write_bytes(b"")
    runner.run_script.return_value = {
        "success": True, "stdout": "not json", "stderr": ""
    }

    result = tools["import_png"](png_path=str(png), mode="new")

    assert result["success"] is False
    assert "Failed to parse size" in result["error"]
    # 验证清理了会话，避免泄漏
    session_manager.close_session.assert_called_once()


def test_import_png_new_mode_lua_error_cleans_session(setup, tmp_path):
    """new 模式 Lua 输出 error 字段时清理会话。"""
    tools, session_manager, runner = setup
    png = tmp_path / "err.png"
    png.write_bytes(b"")
    runner.run_script.return_value = {
        "success": True, "stdout": '{"error":"failed to open png"}', "stderr": ""
    }

    result = tools["import_png"](png_path=str(png), mode="new")

    assert result["success"] is False
    assert "failed to open png" in result["error"]
    session_manager.close_session.assert_called_once()


def test_import_png_stamp_mode_calls_runner(setup, tmp_path):
    """stamp 模式：把 PNG 贴到已有会话的指定位置。"""
    tools, session_manager, runner = setup
    png = tmp_path / "stamp.png"
    png.write_bytes(b"")
    runner.run_script.return_value = {
        "success": True, "stdout": '{"ok":"stamped png onto layer 2 frame 3 at (5,6)"}', "stderr": ""
    }

    result = tools["import_png"](
        png_path=str(png), mode="stamp",
        session_id="test-session-id",
        layer=2, frame=3, offset_x=5, offset_y=6,
    )

    assert result["success"] is True
    assert result["stamped_at"] == {
        "layer": 2, "frame": 3, "offset_x": 5, "offset_y": 6
    }
    # 验证传给 Lua 的参数
    params = runner.run_script.call_args[0][1]
    assert params["mode"] == "stamp"
    assert params["layer"] == "2"
    assert params["frame"] == "3"
    assert params["offset_x"] == "5"
    assert params["offset_y"] == "6"


def test_import_png_stamp_mode_missing_session_id(setup, tmp_path):
    """stamp 模式缺 session_id 报错。"""
    tools, session_manager, runner = setup
    png = tmp_path / "s.png"
    png.write_bytes(b"")

    result = tools["import_png"](png_path=str(png), mode="stamp")

    assert result["success"] is False
    assert "session_id is required" in result["error"]


def test_import_png_invalid_mode(setup, tmp_path):
    """非法 mode 报错。"""
    tools, session_manager, runner = setup
    png = tmp_path / "s.png"
    png.write_bytes(b"")

    result = tools["import_png"](png_path=str(png), mode="bogus")

    assert result["success"] is False
    assert "invalid mode" in result["error"]


def test_import_png_file_not_found(setup):
    """png 文件不存在时报错，且不调用 runner。"""
    tools, session_manager, runner = setup

    result = tools["import_png"](png_path="/nonexistent/file.png", mode="new")

    assert result["success"] is False
    assert "png not found" in result["error"]
    runner.run_script.assert_not_called()
