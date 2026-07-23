"""WebSocket 桥接模块测试。

测试内容：
1. params_to_lua / unescape_text 单元测试
2. WebSocketBridge 集成测试（用 Python websockets client 模拟 Aseprite 扩展）
3. WebSocketRunner 接口测试
4. Config 模式切换测试
"""

import asyncio
import threading
import time

import pytest

from src.bridge import (
    WebSocketBridge,
    params_to_lua,
    unescape_text,
    _WEBSOCKETS_AVAILABLE,
)
from src.config import Config
from src.runner import WebSocketRunner


# ============================================================
# 单元测试：params_to_lua
# ============================================================


class TestParamsToLua:
    """测试 Python dict → Lua table literal 转换。"""

    def test_empty_dict(self):
        assert params_to_lua({}) == "{}"

    def test_int_values(self):
        result = params_to_lua({"x": 10, "y": 20})
        assert "x = 10" in result
        assert "y = 20" in result

    def test_string_values(self):
        result = params_to_lua({"color": "#FF0000", "file": "canvas.ase"})
        assert 'color = "#FF0000"' in result
        assert 'file = "canvas.ase"' in result

    def test_bool_values(self):
        result = params_to_lua({"visible": True, "hidden": False})
        assert "visible = true" in result
        assert "hidden = false" in result

    def test_float_values(self):
        result = params_to_lua({"scale": 1.5})
        assert "scale = 1.5" in result

    def test_none_values(self):
        result = params_to_lua({"optional": None})
        assert "optional = nil" in result

    def test_string_escaping(self):
        """字符串中的特殊字符应被正确转义。"""
        result = params_to_lua({"path": 'C:\\temp\\file.txt'})
        assert 'path = "C:\\\\temp\\\\file.txt"' in result

    def test_string_with_quotes(self):
        result = params_to_lua({"name": 'hello "world"'})
        assert 'name = "hello \\"world\\""' in result

    def test_string_with_newline(self):
        result = params_to_lua({"text": "line1\nline2"})
        assert 'text = "line1\\nline2"' in result

    def test_string_with_tab(self):
        result = params_to_lua({"text": "a\tb"})
        assert 'text = "a\\tb"' in result


# ============================================================
# 单元测试：unescape_text
# ============================================================


class TestUnescapeText:
    """测试转义文本的反转义。"""

    def test_empty(self):
        assert unescape_text("") == ""
        assert unescape_text(None) == ""

    def test_plain_text(self):
        assert unescape_text("hello world") == "hello world"

    def test_tab(self):
        assert unescape_text("a\\tb") == "a\tb"

    def test_newline(self):
        assert unescape_text("line1\\nline2") == "line1\nline2"

    def test_carriage_return(self):
        assert unescape_text("a\\rb") == "a\rb"

    def test_backslash(self):
        assert unescape_text("C:\\\\temp") == "C:\\temp"

    def test_mixed(self):
        assert unescape_text("a\\tb\\nc\\\\d") == "a\tb\nc\\d"

    def test_roundtrip(self):
        """转义→反转义应恢复原值。"""
        original = "OK: drew pixel at (10, 20)"
        # 模拟 Lua 端的 escape_text
        escaped = original.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
        assert unescape_text(escaped) == original


# ============================================================
# 集成测试：WebSocketBridge（需要 websockets 库）
# ============================================================


@pytest.fixture
def bridge_server():
    """启动一个真实的 WebSocketBridge server 用于测试。

    使用非默认端口避免冲突。
    """
    if not _WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")

    bridge = WebSocketBridge(host="127.0.0.1", port=9876)
    assert bridge.start(timeout=3.0)
    yield bridge
    bridge.stop()
    time.sleep(0.2)  # 等待端口释放


@pytest.fixture
def mock_aseprite_client(bridge_server):
    """模拟 Aseprite 扩展：连接到 bridge server，响应请求。

    收到请求后，解析 script_name 和 params，执行一个简化的"脚本"逻辑，
    返回响应。
    """
    if not _WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")

    import websockets

    received_messages = []
    stop_event = threading.Event()

    async def run_client():
        uri = "ws://127.0.0.1:9876"
        try:
            async with websockets.connect(uri) as ws:
                # 循环接收请求，直到收到停止信号或连接关闭
                while not stop_event.is_set():
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break

                    received_messages.append(message)

                    # 解析请求: <id>\t<script_name>\t<lua_table_literal>
                    parts = message.split("\t", 2)
                    req_id = parts[0]
                    script_name = parts[1]

                    # 根据脚本名返回不同的响应
                    if "not_found" in script_name:
                        response = f"{req_id}\tfalse\t\terror: script not found"
                    else:
                        # 成功响应
                        stdout = f"OK: executed {script_name}"
                        response = f"{req_id}\ttrue\t{stdout}\t"

                    await ws.send(response)
        except Exception:
            pass  # 连接关闭等异常，静默退出

    # 在单独的线程中运行 client
    client_loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(client_loop)
        client_loop.run_until_complete(run_client())

    client_thread = threading.Thread(target=run_loop, daemon=True)
    client_thread.start()

    # 等待 client 连接到 server
    time.sleep(0.3)

    yield received_messages

    # 优雅停止：设置停止信号，等待协程自然退出
    stop_event.set()
    client_thread.join(timeout=3.0)
    # 取消所有剩余任务
    try:
        pending = asyncio.all_tasks(client_loop)
        for task in pending:
            task.cancel()
        if pending:
            client_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    client_loop.close()


class TestWebSocketBridgeIntegration:
    """WebSocketBridge 集成测试。"""

    def test_bridge_starts(self, bridge_server):
        """Bridge server 能正常启动。"""
        assert bridge_server is not None
        assert bridge_server._loop is not None

    def test_no_client_connected(self, bridge_server):
        """无 client 连接时，send_request 返回错误。"""
        result = bridge_server.send_request("test.lua", {"x": 1}, timeout=1.0)
        assert result["success"] is False
        assert "not connected" in result["error"].lower()

    def test_request_response_cycle(self, bridge_server, mock_aseprite_client):
        """完整的请求-响应流程。"""
        # 等待 client 连接
        time.sleep(0.5)

        result = bridge_server.send_request(
            "draw_pixel.lua",
            {"x": 10, "y": 20, "color": "#FF0000"},
            timeout=3.0,
        )

        assert result["success"] is True
        assert "OK: executed draw_pixel.lua" in result["stdout"]

    def test_request_with_special_chars(self, bridge_server, mock_aseprite_client):
        """参数含特殊字符（路径、引号）时能正确传输。"""
        time.sleep(0.5)

        result = bridge_server.send_request(
            "create_sprite.lua",
            {"file": "C:\\temp\\canvas.ase", "name": 'test "quote"'},
            timeout=3.0,
        )

        assert result["success"] is True
        # 验证 client 收到了消息
        assert len(mock_aseprite_client) > 0


class TestWebSocketRunner:
    """WebSocketRunner 接口测试。"""

    def test_runner_interface_matches_cli(self):
        """WebSocketRunner 的 run_script 返回格式与 AsepriteRunner 一致。"""
        # 用 mock bridge
        class MockBridge:
            def is_connected(self):
                return True

            def send_request(self, script_name, params, timeout=30.0):
                return {
                    "success": True,
                    "stdout": "OK: test passed",
                    "stderr": "",
                }

        config = Config()
        runner = WebSocketRunner(bridge=MockBridge(), config=config)

        result = runner.run_script("test.lua", {"x": 1})

        assert result["success"] is True
        assert result["stdout"] == "OK: test passed"
        assert result["stderr"] == ""
        assert "error" not in result

    def test_runner_handles_failure(self):
        """失败时返回 error 字段。"""
        class MockBridge:
            def is_connected(self):
                return True

            def send_request(self, script_name, params, timeout=30.0):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "some error",
                    "error": "Script failed",
                }

        config = Config()
        runner = WebSocketRunner(bridge=MockBridge(), config=config)

        result = runner.run_script("test.lua", {"x": 1})

        assert result["success"] is False
        assert result["error"] == "Script failed"
        assert result["stderr"] == "some error"

    def test_runner_handles_disconnected(self):
        """无连接时返回连接错误。"""
        class MockBridge:
            def is_connected(self):
                return False

            def send_request(self, script_name, params, timeout=30.0):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "error": "not connected",
                }

        config = Config()
        runner = WebSocketRunner(bridge=MockBridge(), config=config)

        result = runner.run_script("test.lua", {"x": 1})

        assert result["success"] is False
        assert "not connected" in result["error"]

    def test_runner_constructs_full_path(self):
        """Runner 应构造完整的脚本路径。"""
        captured_path = []

        class MockBridge:
            def is_connected(self):
                return True

            def send_request(self, script_name, params, timeout=30.0):
                captured_path.append(script_name)
                return {"success": True, "stdout": "", "stderr": ""}

        config = Config()
        runner = WebSocketRunner(bridge=MockBridge(), config=config)

        runner.run_script("draw_pixel.lua", {"x": 1})

        # 验证传给 bridge 的是完整路径
        assert len(captured_path) == 1
        assert captured_path[0].endswith("draw_pixel.lua")
        # 应包含 scripts 目录的绝对路径
        assert "scripts" in captured_path[0].replace("\\", "/")

    def test_check_aseprite_exists(self):
        """check_aseprite_exists 应委托给 bridge.is_connected。"""
        class MockBridge:
            def __init__(self, connected):
                self._connected = connected

            def is_connected(self):
                return self._connected

        config = Config()
        runner_connected = WebSocketRunner(bridge=MockBridge(True), config=config)
        runner_disconnected = WebSocketRunner(bridge=MockBridge(False), config=config)

        assert runner_connected.check_aseprite_exists() is True
        assert runner_disconnected.check_aseprite_exists() is False


# ============================================================
# Config 模式测试
# ============================================================


class TestConfigMode:
    """测试 Config 的模式切换。"""

    def test_default_mode_is_cli(self, monkeypatch):
        """默认模式应为 cli。"""
        monkeypatch.delenv("ASEPRITE_MCP_MODE", raising=False)
        config = Config()
        assert config.mode == "cli"

    def test_ws_mode_via_env(self, monkeypatch):
        """通过环境变量切换到 ws 模式。"""
        monkeypatch.setenv("ASEPRITE_MCP_MODE", "ws")
        config = Config()
        assert config.mode == "ws"

    def test_ws_host_port_defaults(self, monkeypatch):
        """ws 模式默认地址和端口。"""
        monkeypatch.delenv("ASEPRITE_WS_HOST", raising=False)
        monkeypatch.delenv("ASEPRITE_WS_PORT", raising=False)
        config = Config()
        assert config.ws_host == "127.0.0.1"
        assert config.ws_port == 9001

    def test_ws_host_port_via_env(self, monkeypatch):
        """通过环境变量自定义 ws 地址和端口。"""
        monkeypatch.setenv("ASEPRITE_WS_HOST", "0.0.0.0")
        monkeypatch.setenv("ASEPRITE_WS_PORT", "8080")
        config = Config()
        assert config.ws_host == "0.0.0.0"
        assert config.ws_port == 8080
