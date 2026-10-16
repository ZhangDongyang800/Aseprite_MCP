"""Bridge protocol hygiene: stdout stays clean, malformed replies fail fast, one client at a time."""

import asyncio
import threading
import time

import pytest

from src.bridge import WebSocketBridge

_WEBSOCKETS_AVAILABLE = True
try:  # pragma: no cover - import guard mirrors tests/test_bridge.py
    import websockets  # noqa: F401
except ImportError:  # pragma: no cover
    _WEBSOCKETS_AVAILABLE = False


def test_diagnostics_never_reach_stdout(capsys):
    bridge = WebSocketBridge(host="127.0.0.1", port=0)
    asyncio.run(bridge._handle_response("req\tfalse\tmalformed"))

    captured = capsys.readouterr()
    assert "[WebSocketBridge]" not in captured.out
    assert "[WebSocketBridge]" in captured.err


def test_startup_banner_goes_to_stderr(capsys):
    bridge = WebSocketBridge(host="127.0.0.1", port=0)
    try:
        assert bridge.start(timeout=5.0) is True
        time.sleep(0.1)
        captured = capsys.readouterr()
        assert "Server listening" not in captured.out
        assert "Server listening" in captured.err
    finally:
        bridge.stop()


def test_malformed_response_releases_the_waiting_request():
    """A 3-field reply (older extensions) must fail the request, not hang it for 30s."""
    bridge = WebSocketBridge(host="127.0.0.1", port=0)
    event = threading.Event()
    box: dict = {}
    bridge._pending["req1"] = (event, box)

    asyncio.run(bridge._handle_response("req1\tfalse\tmalformed response"))

    assert event.wait(1.0) is True
    assert box["result"]["success"] is False
    assert "malformed" in box["result"]["error"].lower()
    assert "req1" not in bridge._pending


def test_response_for_unknown_id_is_logged_not_fatal(capsys):
    bridge = WebSocketBridge(host="127.0.0.1", port=0)
    asyncio.run(bridge._handle_response("nobody\ttrue\tOK\t"))
    captured = capsys.readouterr()
    assert "nobody" in captured.err


@pytest.mark.skipif(not _WEBSOCKETS_AVAILABLE, reason="websockets not installed")
def test_new_client_takes_over_and_closes_the_previous_connection():
    bridge = WebSocketBridge(host="127.0.0.1", port=0)

    class SlowWS:
        def __init__(self):
            self.closed = False
            self.remote_address = ("127.0.0.1", 1234)

        async def close(self):
            self.closed = True

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(30)  # stay connected for the length of the test
            raise StopAsyncIteration

    async def scenario():
        old, new = SlowWS(), SlowWS()
        old_task = asyncio.create_task(bridge._handle_client(old))
        await asyncio.sleep(0.01)
        new_task = asyncio.create_task(bridge._handle_client(new))
        await asyncio.sleep(0.01)
        try:
            assert old.closed is True, "stale extension connection must be closed on takeover"
            assert bridge._client is new
        finally:
            old_task.cancel()
            new_task.cancel()
            await asyncio.gather(old_task, new_task, return_exceptions=True)

    asyncio.run(scenario())