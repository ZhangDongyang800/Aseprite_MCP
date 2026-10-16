"""WebSocket 桥接模块。

在 Python 端启动 WebSocket server，等待 Aseprite 扩展作为 client 连接。
连接建立后，MCP 工具通过 WebSocket 向 Aseprite 发送脚本执行请求，
Aseprite 执行后回传结果。

架构：
    ┌─────────┐    MCP(stdio)    ┌──────────────┐   WebSocket    ┌──────────────┐
    │  AI/TRAE │ ───────────────► │ Python MCP   │ ─────────────► │ Aseprite 扩展 │
    │          │ ◄─────────────── │ Server       │ ◄──────────── │ (ws client)  │
    └─────────┘                   └──────────────┘                └──────────────┘

消息协议（基于文本行）：
    请求（Python → Aseprite）: <id>\t<script_name>\t<lua_table_literal>
    响应（Aseprite → Python）: <id>\t<success>\t<stdout_escaped>\t<stderr_escaped>
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
    """将 Python dict 编码为 Aseprite 扩展可解析的键值对字符串。

    协议：每对参数编码为 key=value，对之间用制表符 \t 分隔。
    因为消息整体按 \t 分隔，所以 key 和 value 内部的 \t 需要先转义。
    支持的类型：bool、int、float、str、None。其他类型转为 str。

    Args:
        d: 参数字典

    Returns:
        编码后的参数字符串，如 'x=10\ty=20\tcolor=#FF0000'
    """
    # 转义键和值中的特殊分隔符/转义符
    # 转义规则（与 Lua 端一致）：
    #   \  -> \\
    #   \t -> \\t
    #   \n -> \\n
    #   \r -> \\r
    #   =  -> \\=  (避免和 key=value 分隔符冲突)
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
    """反转义 Aseprite 端传来的转义文本。

    对应 extension/main.lua 中的 escape_text 函数。

    Args:
        s: 转义后的字符串

    Returns:
        原始字符串
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
    """WebSocket 桥接器。

    在后台线程启动 WebSocket server，管理 Aseprite client 连接，
    提供同步的 send_request 接口供 MCP 工具调用。

    线程模型：
    - 主线程：MCP 工具调用 send_request()（同步阻塞）
    - WebSocket 线程：独立 asyncio 事件循环，处理连接和消息
    - 跨线程通信：threading.Event + 共享 dict
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9001):
        """初始化桥接器。

        Args:
            host: WebSocket server 监听地址
            port: WebSocket server 监听端口
        """
        if not _WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets library is required for WebSocket mode. "
                "Install it with: pip install websockets"
            )

        self.host = host
        self.port = port

        # 当前连接的 Aseprite client（asyncio WebSocket）
        self._client = None
        self._client_lock = threading.Lock()

        # 等待响应的请求：req_id → (threading.Event, result_box)
        self._pending: dict[str, tuple[threading.Event, dict]] = {}
        self._pending_lock = threading.Lock()

        # WebSocket server 的事件循环和线程
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._started = threading.Event()

    def start(self, timeout: float = 5.0) -> bool:
        """在后台线程启动 WebSocket server。

        Args:
            timeout: 等待 server 启动的超时时间（秒）

        Returns:
            True 如果 server 启动成功
        """
        if self._thread is not None:
            return True

        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        return self._started.wait(timeout)

    def _run_server(self):
        """WebSocket server 线程主函数。"""
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
        """启动 WebSocket server 并持续运行。"""
        self._server = await serve(self._handle_client, self.host, self.port)
        self._started.set()
        _log(f"Server listening on ws://{self.host}:{self.port}")
        _log("Waiting for Aseprite extension to connect...")

    async def _handle_client(self, ws):
        """处理 Aseprite client 连接。

        每个 Aseprite 实例连接后，持续接收响应消息并分发到对应的等待请求。
        """
        peer = ws.remote_address if hasattr(ws, "remote_address") else "unknown"
        _log(f"Aseprite client connected: {peer}")

        stale = None
        with self._client_lock:
            # 最新优先：旧连接必须被踢掉，否则它仍能抢答 pending 请求
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
        """解析 Aseprite 的响应，唤醒等待的请求。

        响应格式: <id>\t<success>\t<stdout_escaped>\t<stderr_escaped>

        字段不足的畸形响应（扩展早期版本在若干错误分支只写 3 个字段）同样要唤醒等待方，
        否则调用方只能挂到超时才知道出事了。
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
        """检查是否有 Aseprite client 连接。"""
        with self._client_lock:
            return self._client is not None

    def send_request(
        self,
        script_name: str,
        params: dict,
        timeout: float = 30.0,
    ) -> dict:
        """同步发送脚本执行请求到 Aseprite，等待响应。

        Args:
            script_name: Lua 脚本文件名（如 "draw_pixel.lua"）
            params: 脚本参数字典
            timeout: 等待响应的超时时间（秒）

        Returns:
            执行结果字典：
            - 成功: {"success": True, "stdout": "...", "stderr": "..."}
            - 失败: {"success": False, "stdout": "...", "stderr": "...", "error": "..."}
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

        # 构造请求消息: <id>\t<script_name>\t<params_key=value_pairs>
        encoded_params = params_to_lua(params)
        message = f"{req_id}\t{script_name}\t{encoded_params}"

        # 在 WebSocket server 的事件循环中发送消息
        with self._client_lock:
            client = self._client

        if client is None:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            return {"success": False, "stdout": "", "stderr": "", "error": "Connection lost"}

        try:
            future = asyncio.run_coroutine_threadsafe(client.send(message), self._loop)
            future.result(timeout=5.0)  # 发送本身的超时
        except Exception as e:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            return {"success": False, "stdout": "", "stderr": "", "error": f"Failed to send request: {e}"}

        # 等待 Aseprite 执行并回传响应
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
        """停止 WebSocket server。"""
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
