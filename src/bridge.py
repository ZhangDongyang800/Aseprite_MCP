"""WebSocket bridge.

Starts a WebSocket server on the Python side and waits for the Aseprite extension to
connect as a client. Once connected, MCP tools send script-execution requests over the
socket, and Aseprite sends the result back.

Architecture:
    ┌─────────┐    MCP(stdio)    ┌──────────────┐   WebSocket    ┌──────────────┐
    │  AI/TRAE │ ───────────────► │ Python MCP   │ ─────────────► │ Aseprite ext. │
    │          │ ◄─────────────── │ Server       │ ◄──────────── │ (ws client)  │
    └─────────┘                   └──────────────┘                └──────────────┘

Message protocol (line-based text):
    Request (Python → Aseprite): <id>\t<script_name>\t<lua_table_literal>
    Response (Aseprite → Python): <id>\t<success>\t<stdout_escaped>\t<stderr_escaped>
"""

import asyncio
import sys
import threading
import uuid
from typing import Optional

try:
    import websockets
    from websockets.asyncio.server import serve
    _WEBSOCKETS_AVAILABLE = True
except ImportError:
    _WEBSOCKETS_AVAILABLE = False


def _log(message: str) -> None:
    """Bridge diagnostics belong on stderr.

    The MCP stdio transport speaks JSON-RPC on stdout; a stray banner or error line there
    is not noise, it is a protocol violation that strict clients reject outright.
    """
    print(f"[WebSocketBridge] {message}", file=sys.stderr, flush=True)


def params_to_lua(d: dict) -> str:
    """Encode a Python dict as key=value pairs the Aseprite extension can parse.

    Protocol: each pair is encoded as key=value and pairs are separated by a tab. Because
    the message itself is split on tabs, tabs inside keys and values have to be escaped
    first. Supported types: bool, int, float, str, None. Anything else becomes str().

    Args:
        d: parameter dict

    Returns:
        the encoded parameter string, e.g. 'x=10\ty=20\tcolor=#FF0000'
    """
    # Escape separators/escape characters inside keys and values.
    # Escape rules (kept in sync with the Lua side):
    #   \  -> \\
    #   \t -> \\t
    #   \n -> \\n
    #   \r -> \\r
    #   =  -> \\=  (so it cannot clash with the key=value separator)
    def _escape(s: str) -> str:
        s = s.replace("\\", "\\\\")
        s = s.replace("\t", "\\t")
        s = s.replace("\n", "\\n")
        s = s.replace("\r", "\\r")
        s = s.replace("=", "\\=")
        return s

    parts = []
    for k, v in d.items():
        if isinstance(v, bool):
            value = "true" if v else "false"
        elif v is None:
            value = ""
        else:
            value = str(v)

        parts.append(f"{_escape(str(k))}={_escape(value)}")
    return "\t".join(parts)


def unescape_text(s: str) -> str:
    """Undo the escaping applied on the Aseprite side.

    Mirrors escape_text in extension/main.lua.

    Args:
        s: the escaped string

    Returns:
        the original string
    """
    if not s:
        return ""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            next_char = s[i + 1]
            if next_char == "t":
                result.append("\t")
            elif next_char == "n":
                result.append("\n")
            elif next_char == "r":
                result.append("\r")
            elif next_char == "\\":
                result.append("\\")
            else:
                result.append(s[i])
                result.append(next_char)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


class WebSocketBridge:
    """WebSocket bridge.

    Runs a WebSocket server in a background thread, tracks the Aseprite client
    connection, and exposes a synchronous send_request for MCP tools.

    Threading model:
    - main thread: MCP tools call send_request() (blocks)
    - WebSocket thread: an independent asyncio event loop handling connections/messages
    - cross-thread hand-off: threading.Event + a shared dict
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9001):
        """Initialise the bridge.

        Args:
            host: address the WebSocket server listens on
            port: port the WebSocket server listens on
        """
        if not _WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets library is required for WebSocket mode. "
                "Install it with: pip install websockets"
            )

        self.host = host
        self.port = port

        # Currently connected Aseprite client (asyncio WebSocket)
        self._client = None
        self._client_lock = threading.Lock()

        # Requests waiting for a response: req_id -> (threading.Event, result_box)
        self._pending: dict[str, tuple[threading.Event, dict]] = {}
        self._pending_lock = threading.Lock()

        # Event loop and thread of the WebSocket server
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._started = threading.Event()

    def start(self, timeout: float = 5.0) -> bool:
        """Start the WebSocket server on a background thread.

        Args:
            timeout: how long to wait for the server to come up (seconds)

        Returns:
            True when the server started successfully
        """
        if self._thread is not None:
            return True

        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        return self._started.wait(timeout)

    def _run_server(self):
        """Body of the WebSocket server thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._serve())
            self._loop.run_forever()
        except Exception as e:
            _log(f"Server error: {e}")
        finally:
            self._loop.close()

    async def _serve(self):
        """Start the WebSocket server and keep it running."""
        self._server = await serve(self._handle_client, self.host, self.port)
        self._started.set()
        _log(f"Server listening on ws://{self.host}:{self.port}")
        _log("Waiting for Aseprite extension to connect...")

    async def _handle_client(self, ws):
        """Handle an Aseprite client connection.

        Once an Aseprite instance connects, it keeps delivering response messages, which
        are dispatched to the request waiting for them.
        """
        peer = ws.remote_address if hasattr(ws, "remote_address") else "unknown"
        _log(f"Aseprite client connected: {peer}")

        stale = None
        with self._client_lock:
            # Newest wins: the old connection has to be kicked, or it can still answer
            # pending requests out of turn
            stale, self._client = self._client, ws
        if stale is not None and stale is not ws:
            _log(f"closing stale client connection {peer}")
            try:
                await stale.close()
            except Exception as e:  # noqa: BLE001 - closing a dead socket must not break takeover
                _log(f"failed to close stale connection: {e}")

        try:
            async for message in ws:
                await self._handle_response(message)
        except Exception as e:
            _log(f"Client connection error: {e}")
        finally:
            with self._client_lock:
                if self._client is ws:
                    self._client = None
            _log(f"Aseprite client disconnected: {peer}")

    async def _handle_response(self, message: str):
        """Parse an Aseprite response and wake the waiting request.

        Response format: <id>\t<success>\t<stdout_escaped>\t<stderr_escaped>

        Malformed responses with missing fields (early extension versions wrote only 3
        fields on a few error branches) have to wake the waiter too, or the caller only
        learns something went wrong when the wait times out.
        """
        parts = message.split("\t", 3)
        req_id = parts[0] if parts else ""
        if len(parts) < 4:
            _log(f"Malformed response ({len(parts)}/4 fields): {message!r}")
            pending = self._take_pending(req_id)
            if pending:
                event, result_box = pending
                result_box["result"] = {
                    "success": False,
                    "stdout": "",
                    "stderr": message,
                    "error": (
                        "Malformed response from the Aseprite extension "
                        "(expected <id>\\t<success>\\t<stdout>\\t<stderr>). "
                        "Update the extension in the Aseprite_MCP/extension folder."
                    ),
                }
                event.set()
            return

        success_str, stdout_escaped, stderr_escaped = parts[1], parts[2], parts[3]
        success = success_str.lower() == "true"
        stdout = unescape_text(stdout_escaped)
        stderr = unescape_text(stderr_escaped)

        pending = self._take_pending(req_id)

        if pending:
            event, result_box = pending
            result_box["result"] = {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
            }
            if not success and not stderr:
                result_box["result"]["error"] = "Script execution failed"
            event.set()
        else:
            _log(f"No pending request for id={req_id}")

    def _take_pending(self, req_id: str):
        """Pop the wait handle for req_id (None when nobody is waiting)."""
        if not req_id:
            return None
        with self._pending_lock:
            return self._pending.pop(req_id, None)

    def is_connected(self) -> bool:
        """Return whether an Aseprite client is connected."""
        with self._client_lock:
            return self._client is not None

    def send_request(
        self,
        script_name: str,
        params: dict,
        timeout: float = 30.0,
    ) -> dict:
        """Send a script-execution request to Aseprite and block until it answers.

        Args:
            script_name: Lua script file name (e.g. "draw_pixel.lua")
            params: script parameter dict
            timeout: how long to wait for the response (seconds)

        Returns:
            result dict:
            - success: {"success": True, "stdout": "...", "stderr": "..."}
            - failure: {"success": False, "stdout": "...", "stderr": "...", "error": "..."}
        """
        if not self.is_connected():
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": "Aseprite extension is not connected. "
                "Please install the extension and click 'MCP Bridge: Toggle Connection' in Aseprite.",
            }

        if self._loop is None:
            return {"success": False, "stdout": "", "stderr": "", "error": "Bridge not started"}

        req_id = str(uuid.uuid4())
        result_box: dict = {}
        event = threading.Event()

        with self._pending_lock:
            self._pending[req_id] = (event, result_box)

        # Build the request: <id>\t<script_name>\t<params_key=value_pairs>
        encoded_params = params_to_lua(params)
        message = f"{req_id}\t{script_name}\t{encoded_params}"

        # Send on the WebSocket server's event loop
        with self._client_lock:
            client = self._client

        if client is None:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            return {"success": False, "stdout": "", "stderr": "", "error": "Connection lost"}

        try:
            future = asyncio.run_coroutine_threadsafe(client.send(message), self._loop)
            future.result(timeout=5.0)  # timeout for the send itself
        except Exception as e:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            return {"success": False, "stdout": "", "stderr": "", "error": f"Failed to send request: {e}"}

        # Wait for Aseprite to run the script and send the response back
        if not event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(req_id, None)
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"Request timeout after {timeout}s. "
                "Aseprite may be busy or the mouse is outside the Aseprite window "
                "(WebSocket callbacks are delayed when Aseprite is not in focus).",
            }

        return result_box.get("result", {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": "No result received",
        })

    def stop(self):
        """Stop the WebSocket server."""
        if self._loop and self._server:

            async def _shutdown():
                await self._server.close()
                # give in-flight connection handlers a beat to unwind; tearing the loop down
                # under them leaves "no running event loop" warnings in the host process
                await asyncio.sleep(0.05)

            try:
                asyncio.run_coroutine_threadsafe(_shutdown(), self._loop).result(timeout=2.0)
            except Exception:
                pass
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
