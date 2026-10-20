"""Tests for the WebSocket bridge module.

Covers:
1. params_to_lua / unescape_text unit tests
2. WebSocketBridge integration tests (a Python websockets client stands in for
   the Aseprite extension)
3. WebSocketRunner interface tests
4. Config mode switching
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
# Unit tests: params_to_lua
# ============================================================


class TestParamsToLua:
    """Python dict -> key=value parameter encoding."""

    def test_empty_dict(self):
        assert params_to_lua({}) == ""

    def test_int_values(self):
        result = params_to_lua({"x": 10, "y": 20})
        assert "x=10" in result
        assert "y=20" in result

    def test_string_values(self):
        result = params_to_lua({"color": "#FF0000", "file": "canvas.ase"})
        assert "color=#FF0000" in result
        assert "file=canvas.ase" in result

    def test_bool_values(self):
        result = params_to_lua({"visible": True, "hidden": False})
        assert "visible=true" in result
        assert "hidden=false" in result

    def test_float_values(self):
        result = params_to_lua({"scale": 1.5})
        assert "scale=1.5" in result

    def test_none_values(self):
        result = params_to_lua({"optional": None})
        assert "optional=" in result

    def test_equals_in_value(self):
        """An equals sign inside a value must be escaped."""
        result = params_to_lua({"formula": "a=b+c"})
        assert "formula=a\\=b+c" in result

    def test_backslash_in_value(self):
        """Backslashes in Windows paths must be escaped."""
        result = params_to_lua({"path": "C:\\temp\\file.txt"})
        assert "path=C:\\\\temp\\\\file.txt" in result

    def test_newline_in_value(self):
        result = params_to_lua({"text": "line1\nline2"})
        assert "text=line1\\nline2" in result

    def test_tab_in_value(self):
        result = params_to_lua({"text": "a\tb"})
        assert "text=a\\tb" in result

    def test_key_with_special_chars(self):
        """Special characters in keys must be escaped too."""
        result = params_to_lua({"my=key": "value"})
        assert "my\\=key=value" in result


# ============================================================
# Unit tests: unescape_text
# ============================================================


class TestUnescapeText:
    """Unescaping of escaped text."""

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
        """Escape -> unescape must restore the original value."""
        original = "OK: drew pixel at (10, 20)"
        # Emulate escape_text on the Lua side
        escaped = original.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
        assert unescape_text(escaped) == original


# ============================================================
# Integration tests: WebSocketBridge (requires the websockets library)
# ============================================================


@pytest.fixture
def bridge_server():
    """Start a real WebSocketBridge server for the test.

    A non-default port is used to avoid clashes.
    """
    if not _WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")

    bridge = WebSocketBridge(host="127.0.0.1", port=9876)
    assert bridge.start(timeout=3.0)
    yield bridge
    bridge.stop()
    time.sleep(0.2)  # wait for the port to be released


def parse_params_from_request(message: str) -> dict:
    """Parse key=value pairs the way the Aseprite extension does.

    Pairs are tab-separated and escape sequences are decoded here.
    """
    # Split the fields and decode escapes in one pass (matches Lua split_message)
    parts = []
    current = []
    i = 0
    while i < len(message):
        c = message[i]
        if c == "\\" and i + 1 < len(message):
            next_c = message[i + 1]
            if next_c == "t":
                current.append("\t")
                i += 2
            elif next_c == "n":
                current.append("\n")
                i += 2
            elif next_c == "r":
                current.append("\r")
                i += 2
            elif next_c == "=":
                current.append("=")
                i += 2
            elif next_c == "\\":
                current.append("\\")
                i += 2
            else:
                current.append(c)
                i += 1
        elif c == "\t":
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(c)
            i += 1
    parts.append("".join(current))

    params = {}
    for part in parts[2:]:
        eq_pos = part.find("=")
        if eq_pos >= 0:
            key = part[:eq_pos]
            value = part[eq_pos + 1 :]
            params[key] = value
    return params


@pytest.fixture
def mock_aseprite_client(bridge_server):
    """Stand in for the Aseprite extension: connect to the bridge, answer requests.

    On each request it parses script_name and params, runs a simplified
    "script" and sends a response back.
    """
    if not _WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")

    import websockets

    received_messages = []
    received_params = []
    stop_event = threading.Event()

    async def run_client():
        uri = "ws://127.0.0.1:9876"
        try:
            async with websockets.connect(uri) as ws:
                # Keep receiving requests until asked to stop or the connection closes
                while not stop_event.is_set():
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break

                    received_messages.append(message)
                    params = parse_params_from_request(message)
                    received_params.append(params)

                    # Request format: <id>\t<script_name>\t<key=value pairs>
                    parts = message.split("\t", 2)
                    req_id = parts[0]
                    script_name = parts[1]

                    # Return a different response depending on the script name
                    if "not_found" in script_name:
                        response = f"{req_id}\tfalse\t\terror: script not found"
                    else:
                        # Success response
                        stdout = f"OK: executed {script_name}"
                        response = f"{req_id}\ttrue\t{stdout}\t"

                    await ws.send(response)
        except Exception:
            pass  # connection closed or similar; exit silently

    # Run the client on its own thread
    client_loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(client_loop)
        client_loop.run_until_complete(run_client())

    client_thread = threading.Thread(target=run_loop, daemon=True)
    client_thread.start()

    # Wait for the client to connect to the server
    time.sleep(0.3)

    yield {"messages": received_messages, "params": received_params}

    # Stop gracefully: set the stop flag and let the coroutine exit on its own
    stop_event.set()
    client_thread.join(timeout=3.0)
    # Cancel whatever tasks are left
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
    """WebSocketBridge integration tests."""

    def test_bridge_starts(self, bridge_server):
        """The bridge server starts."""
        assert bridge_server is not None
        assert bridge_server._loop is not None

    def test_no_client_connected(self, bridge_server):
        """With no client connected, send_request returns an error."""
        result = bridge_server.send_request("test.lua", {"x": 1}, timeout=1.0)
        assert result["success"] is False
        assert "not connected" in result["error"].lower()

    def test_request_response_cycle(self, bridge_server, mock_aseprite_client):
        """A full request-response round trip."""
        # Wait for the client to connect
        time.sleep(0.5)

        result = bridge_server.send_request(
            "draw_pixel.lua",
            {"x": 10, "y": 20, "color": "#FF0000"},
            timeout=3.0,
        )

        assert result["success"] is True
        assert "OK: executed draw_pixel.lua" in result["stdout"]

    def test_request_with_special_chars(self, bridge_server, mock_aseprite_client):
        """Parameters with special characters (paths, equals signs) survive the trip."""
        time.sleep(0.5)

        result = bridge_server.send_request(
            "create_sprite.lua",
            {"file": "C:\\temp\\canvas.ase", "formula": "a=b+c"},
            timeout=3.0,
        )

        assert result["success"] is True
        # The client received the message
        assert len(mock_aseprite_client["messages"]) > 0
        # The parameters parsed back correctly
        params = mock_aseprite_client["params"][-1]
        assert params["file"] == "C:\\temp\\canvas.ase"
        assert params["formula"] == "a=b+c"


class TestWebSocketRunner:
    """WebSocketRunner interface tests."""

    def test_runner_interface_matches_cli(self):
        """WebSocketRunner.run_script returns the same shape as AsepriteRunner."""
        # Use a mock bridge
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
        """A failure carries an error field."""
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
        """With no connection it reports a connection error."""
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
        """The runner builds the full script path."""
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

        # What reaches the bridge is the full path
        assert len(captured_path) == 1
        assert captured_path[0].endswith("draw_pixel.lua")
        # It must contain the absolute scripts dir
        assert "scripts" in captured_path[0].replace("\\", "/")

    def test_check_aseprite_exists(self):
        """check_aseprite_exists delegates to bridge.is_connected."""
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
# Config mode tests
# ============================================================


class TestConfigMode:
    """Config mode switching."""

    def test_default_mode_is_cli(self, monkeypatch):
        """The default mode is cli."""
        monkeypatch.delenv("ASEPRITE_MCP_MODE", raising=False)
        config = Config()
        assert config.mode == "cli"

    def test_ws_mode_via_env(self, monkeypatch):
        """The env var switches to ws mode."""
        monkeypatch.setenv("ASEPRITE_MCP_MODE", "ws")
        config = Config()
        assert config.mode == "ws"

    def test_ws_host_port_defaults(self, monkeypatch):
        """Default ws host and port."""
        monkeypatch.delenv("ASEPRITE_WS_HOST", raising=False)
        monkeypatch.delenv("ASEPRITE_WS_PORT", raising=False)
        config = Config()
        assert config.ws_host == "127.0.0.1"
        assert config.ws_port == 9001

    def test_ws_host_port_via_env(self, monkeypatch):
        """The ws host and port can be customized through the env vars."""
        monkeypatch.setenv("ASEPRITE_WS_HOST", "0.0.0.0")
        monkeypatch.setenv("ASEPRITE_WS_PORT", "8080")
        config = Config()
        assert config.ws_host == "0.0.0.0"
        assert config.ws_port == 8080
