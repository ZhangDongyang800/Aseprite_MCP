"""Websocket-bridge probe: protocol, simulated extension, error quality, CLI fallback.

Parts
  1. unit - a malformed 3-field response must wake the waiter instead of hanging it
  2. ws end-to-end against a SIMULATED extension (a fake ws client that runs the script
     it receives through real `aseprite -b`) - framing, param escaping, response parsing,
     envelope mode=ws, inspect and run_lua over the bridge
  3. ws server with no extension attached - error message quality and fail-fast
  4. ws port occupied - fallback to CLI (spec P0-8) plus a real op through the fallback

The real extension/main.lua needs a GUI Aseprite session, so extension-side Lua is
covered by code review only; parts 2-4 drive the same scripts the extension would run.

    python tests/live/ws_probe.py            # all parts
    python tests/live/ws_probe.py 2          # one part
"""
import asyncio
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness import ROOT, Report, finish, metrics_of, require_aseprite  # noqa: E402

ASEPRITE = require_aseprite()


def _unescape(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append({"t": "\t", "n": "\n", "r": "\r", "\\": "\\", "=": "="}
                       .get(s[i + 1], "\\" + s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _escape(s: str) -> str:
    s = s or ""
    for a, b in (("\\", "\\\\"), ("\t", "\\t"), ("\n", "\\n"), ("\r", "\\r")):
        s = s.replace(a, b)
    return s


def _parse_request(message: str):
    """Mirror of the extension's parser: split at the first *unescaped* '='."""
    parts = message.split("\t")
    req_id, script, params = parts[0], parts[1], {}
    for part in parts[2:]:
        i = 0
        while i < len(part):
            if part[i] == "\\":
                i += 2
                continue
            if part[i] == "=":
                break
            i += 1
        params[_unescape(part[:i])] = _unescape(part[i + 1:])
    return req_id, script, params


async def _fake_extension(url: str, log: list):
    """Simulated Aseprite extension: read requests, run real aseprite -b, reply 4 fields."""
    import websockets

    ws = None
    for attempt in range(20):
        try:
            ws = await websockets.connect(url)
            break
        except Exception as exc:  # noqa: BLE001 - the bridge may still be binding
            log.append(f"connect {attempt + 1} failed: {type(exc).__name__}")
            await asyncio.sleep(0.5)
    if ws is None:
        log.append("CONNECT FAILED")
        return
    async with ws:
        log.append("connected")
        async for message in ws:
            req_id, script, params = _parse_request(message)
            log.append(f"req {req_id} script={os.path.basename(script)} params={list(params)}")
            cmd = [ASEPRITE, "-b"]
            for k, v in params.items():          # --script-param MUST precede --script
                cmd.extend(["--script-param", f"{k}={v}"])
            cmd.extend(["--script", script])
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=40)
                ok, stdout, stderr = proc.returncode == 0, proc.stdout or "", proc.stderr or ""
            except subprocess.TimeoutExpired:
                ok, stdout, stderr = False, "", "fake-extension: script timeout"
            await ws.send(f"{req_id}\t{str(ok).lower()}\t{_escape(stdout)}\t{_escape(stderr)}")
            log.append(f"resp {req_id} ok={ok}")


def _transport(mode: str, port: int):
    from fastmcp.client.transports import StdioTransport

    env = dict(os.environ)
    env.pop("ASEPRITE_MCP_MODE", None)
    env.update({"ASEPRITE_MCP_MODE": mode, "ASEPRITE_WS_PORT": str(port),
                "ASEPRITE_PATH": ASEPRITE,
                "ASEPRITE_WORK_DIR": str(Path(__file__).resolve().parent / ".build" / "work")})
    return StdioTransport(command=sys.executable, args=[str(ROOT / "server.py")], env=env)


# ------------------------------------------------------------------ part 1
def part1_unit() -> Report:
    """A 3-field response (what old extension builds send on error) must not hang."""
    r = Report("ws part 1: malformed response")
    sys.path.insert(0, str(ROOT))
    from src.bridge import WebSocketBridge, unescape_text

    # the wire only ever escapes \ \t \n \r (the '=' separator is request-side only)
    r.equal("unescape handles the wire escapes", unescape_text("a\\tb\\nc\\rd\\\\e"), "a\tb\nc\rd\\e")
    r.equal("escape -> unescape round trip",
            unescape_text(_escape("line1\nline2\tcol\\end")), "line1\nline2\tcol\\end")

    async def run():
        bridge = WebSocketBridge(host="127.0.0.1", port=9999)
        event, box = threading.Event(), {}
        bridge._pending["req1"] = (event, box)
        await bridge._handle_response("req1\tfalse\terror: script not found: /x/y.lua")
        return bridge, event, box

    bridge, event, box = asyncio.run(run())
    r.check("malformed response wakes the waiter", event.is_set(), "waiter still blocked")
    r.check("pending slot cleared", "req1" not in bridge._pending, list(bridge._pending))
    r.equal("malformed response is a failure", (box.get("result") or {}).get("success"), False)
    r.contains("tells the operator to update the extension",
               (box.get("result") or {}).get("error", ""), "extension")

    async def run_valid():
        event, box = threading.Event(), {}
        bridge._pending["req2"] = (event, box)
        # tabs inside stdout must arrive escaped, since \t is the field separator
        await bridge._handle_response("req2\ttrue\tsome\\tstdout\\n\\tmore\tstderr\\there")
        return event, box

    event, box = asyncio.run(run_valid())
    r.check("valid 4-field response resolves", event.is_set())
    r.equal("stdout is unescaped", (box.get("result") or {}).get("stdout"),
            "some\tstdout\n\tmore")
    r.equal("stderr is unescaped", (box.get("result") or {}).get("stderr"), "stderr\there")
    return r


# ------------------------------------------------------------------ part 2
async def part2_connected() -> Report:
    r = Report("ws part 2: simulated extension")
    from fastmcp import Client

    port = 9161
    log: list = []
    async with Client(_transport("ws", port)) as c:
        ext = asyncio.create_task(_fake_extension(f"ws://127.0.0.1:{port}", log))
        await asyncio.sleep(2.0)
        r.check("extension connected", any("connected" in line for line in log), log[:5])

        env = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": 24, "height": 24},
            {"op": "draw_rect", "x": 2, "y": 2, "width": 20, "height": 20,
             "color": "#29ADFF", "filled": True},
        ]})).structured_content or {}
        sid = env.get("session_id")
        r.check("batch over the bridge ok", env.get("ok") is True, env.get("error"))
        r.equal("envelope says ws mode", env.get("mode"), "ws")
        r.check("bridge really carried the script",
                any(f"req" in line for line in log), log[:8])

        sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 2})).structured_content or {}
        r.check("inspect works over ws", sc.get("ok") is True, sc.get("error"))
        r.check("inspect sees the color", len(metrics_of(sc).get("palette") or []) >= 1,
                metrics_of(sc).get("palette"))

        env = (await c.call_tool("run_lua", {"session_id": sid,
                                             "code": 'print("w=" .. app.activeSprite.width)',
                                             "unsafe": True, "confirmed": True})).structured_content or {}
        r.check("run_lua over ws ok", env.get("ok") is True, env.get("error"))
        r.contains("run_lua printed the width", json_dump(env), "w=24")

        env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
            {"op": "draw_pixel", "x": 5, "y": 5, "color": "#FF0000"},
            {"op": "draw_pixel", "x": 5, "y": 5, "color": "#FF0000", "layer": 7},
        ]})).structured_content or {}
        r.check("failed ws batch is reported", env.get("ok") is False, env.get("error"))

        env = (await c.call_tool("apply_operations", {"session_id": sid,
                                                       "ops": [{"op": "close_session"}],
                                                       "confirmed": True})).structured_content or {}
        r.check("close_session over ws ok", env.get("ok") is True, env.get("error"))
        ext.cancel()
    return r


def json_dump(env: dict) -> str:
    import json
    return json.dumps(env, ensure_ascii=False, default=str)


# ------------------------------------------------------------------ part 3
async def part3_not_connected() -> Report:
    r = Report("ws part 3: no extension attached")
    from fastmcp import Client

    async with Client(_transport("ws", 9162)) as c:
        t0 = time.time()
        env = (await c.call_tool("apply_operations", {
            "ops": [{"op": "create_sprite", "width": 8, "height": 8}]})).structured_content or {}
        elapsed = round(time.time() - t0, 2)
        r.check("call fails fast instead of hanging", elapsed < 15, f"{elapsed}s")
        r.check("error is explained", env.get("ok") is False, env.get("error"))
        message = str((env.get("error") or {}).get("message", ""))
        r.contains("error mentions the extension", message.lower(), "extension")
    return r


# ------------------------------------------------------------------ part 4
def part4_fallback() -> Report:
    """Occupied ws port -> the runner must fall back to CLI and still work (spec P0-8)."""
    r = Report("ws part 4: CLI fallback")
    import tempfile

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 9163))
    sock.listen(1)
    try:
        os.environ["ASEPRITE_PATH"] = ASEPRITE
        os.environ["ASEPRITE_WS_PORT"] = "9163"
        os.environ["ASEPRITE_MCP_MODE"] = "ws"
        os.environ["ASEPRITE_WORK_DIR"] = tempfile.mkdtemp(prefix="wsfallback_")

        sys.path.insert(0, str(ROOT))
        import src.v2.ops  # noqa: F401 - registers the ops
        from src.bridge import WebSocketBridge
        from src.config import Config
        from src.runner import AsepriteRunner, WebSocketRunner
        from src.session import SessionManager
        from src.v2.executor import Engine

        cfg = Config()
        cfg.mode, cfg.ws_port = "ws", 9163
        bridge = WebSocketBridge(host=cfg.ws_host, port=cfg.ws_port)
        started = bridge.start(timeout=5.0)
        r.check("bridge refuses to start on a busy port", started is False, started)
        if started:
            return r
        cfg.mode = "cli"
        runner = AsepriteRunner(cfg)

        manager = SessionManager(cfg)
        sid = manager.create_session(width=8, height=8, color_mode="rgb")
        # the session only owns a path; the document itself is created by the op
        # (draw_pixel on a non-existent .ase is a clean "call create_sprite first")
        env = Engine(manager, runner, cfg).apply(sid, [
            {"op": "create_sprite", "width": 8, "height": 8, "color_mode": "rgb",
             "file": str(manager.get_ase_path(sid))},
            {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
        ])
        r.check("a real op still works through the fallback", env.ok,
                getattr(env, "error", None) and env.error.message)
        r.equal("envelope advertises file_snapshot undo", env.undo.mode, "file_backup")
        r.equal("fallback runner is the CLI one", env.mode, "cli")
        manager.close_session(sid)
    finally:
        sock.close()
    return r


PARTS = {"1": part1_unit, "2": lambda: asyncio.run(part2_connected()),
         "3": lambda: asyncio.run(part3_not_connected()), "4": part4_fallback}


if __name__ == "__main__":
    which = sys.argv[1:] or list(PARTS)
    reports = []
    for key in which:
        if key not in PARTS:
            sys.exit(f"unknown part {key}; available: {', '.join(PARTS)}")
        try:
            reports.append(PARTS[key]())
        except Exception as exc:  # noqa: BLE001 - report, never explode
            bad = Report(f"ws part {key}")
            bad.check("part ran", False, f"{type(exc).__name__}: {exc}")
            reports.append(bad)
    sys.exit(finish(reports))