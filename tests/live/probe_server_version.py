"""Is the repo build behaving as specified? (version probe)

The MCP server a client is connected to keeps running the code it loaded at startup, so
"pulled new commits but the tools still feel old" is a real failure mode. This script
ignores whatever is connected and starts a **fresh** server from this working tree, then
asserts the four behaviours that the current build changed:

  1. out-of-canvas drawing fails with a readable reason (and no phantom transaction warning)
  2. atomic=false keeps the ops that worked instead of discarding everything
  3. a clean batch emits no warnings at all
  4. paint_grid from outside the server work dir requires confirmed=true

    python tests/live/probe_server_version.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness import Report, finish, transport  # noqa: E402


async def main() -> int:
    from fastmcp import Client

    r = Report("server version")
    async with Client(transport()) as c:
        # 1) out-of-canvas draw: clean message, no bogus warnings
        env = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": 16, "height": 16},
            {"op": "draw_pixel", "x": 99, "y": 3, "color": "#FF0000"},
        ]})).structured_content or {}
        err = env.get("error") or {}
        r.check("oob draw fails", env.get("ok") is False, brief_error(env))
        r.contains("oob draw says why", err.get("message", ""), "outside")
        r.equal("no transaction warning", env.get("warnings"), [])

        # the failed auto-created batch must not leave a session behind
        try:
            again = (await c.call_tool("apply_operations", {
                "session_id": env.get("session_id") or "no-such-session",
                "ops": [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#000000"}],
            })).structured_content or {}
            r.check("orphan session reclaimed", again.get("ok") is False,
                    f"session {env.get('session_id')} still accepts ops")
        except Exception as exc:  # noqa: BLE001 - the tool may reject unknown sessions
            r.check("orphan session reclaimed", True, type(exc).__name__)

        # 2) atomic=false -> partial success
        env = (await c.call_tool("apply_operations", {
            "ops": [{"op": "create_sprite", "width": 16, "height": 16}]})).structured_content or {}
        sid = env.get("session_id")
        env = (await c.call_tool("apply_operations", {"session_id": sid, "atomic": False, "ops": [
            {"op": "draw_pixel", "x": 0, "y": 0, "color": "#FF0000"},
            {"op": "draw_pixel", "x": 5, "y": 5, "color": "#00FF00", "layer": 9},
            {"op": "draw_pixel", "x": 15, "y": 15, "color": "#FF00FF"},
        ]})).structured_content or {}
        warns = env.get("warnings") or []
        r.check("atomic=false reports ok", env.get("ok") is True, brief_error(env))
        r.check("atomic=false warns about partial success",
                any("partial success" in w for w in warns), warns)

        # 3) clean batch: silent
        env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
            {"op": "draw_rect", "x": 2, "y": 2, "width": 4, "height": 4, "color": "#00FF00"}],
        })).structured_content or {}
        r.check("clean batch ok", env.get("ok") is True, brief_error(env))
        r.equal("clean batch is silent", env.get("warnings"), [])

        # 4) paint_grid gate (an error envelope, not an exception: the gate runs
        #    before any Lua, so a missing file never even gets opened)
        env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
            {"op": "paint_grid", "path": "D:/definitely/not/in/work/dir.lua"}],
        })).structured_content or {}
        r.equal("paint_grid outside work dir is gated",
                (env.get("error") or {}).get("code"), "confirmation_required")

        # inspect must come back with metrics (tool returns them at top level)
        ins = (await c.call_tool("inspect", {"session_id": sid, "scale": 1})).structured_content or {}
        r.check("inspect returns metrics", ins.get("ok") is True and "metrics" in ins,
                sorted(ins))

        await c.call_tool("apply_operations", {"session_id": sid,
                                               "ops": [{"op": "close_session"}],
                                               "confirmed": True})

    return finish([r])


def brief_error(env: dict) -> str:
    err = env.get("error") or {}
    return f"{err.get('code')}: {str(err.get('message'))[:120]}"


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))