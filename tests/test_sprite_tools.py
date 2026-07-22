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
