"""On-machine regression scenarios: real MCP stdio + real Aseprite.

Each scenario asserts the contract it is named after (undo bookkeeping, partial success,
rollback, bounds checking, confirmation gates, animation metadata, run_lua snapshot
safety, and the timings the review flagged). Print-friendly report + exit code.

    python tests/live/live_smoke.py                 # default: core
    python tests/live/live_smoke.py bounds gates runlua
    python tests/live/live_smoke.py --all

Headless `aseprite -b` has no undo history at all, so CLI-mode undo/redo are file-snapshot
swaps; the native-history scenarios only make sense in live (`ASEPRITE_MCP_MODE=ws`)
mode against a GUI Aseprite with the extension loaded.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness import ENVELOPE_FIELDS, Report, brief, finish, metrics_of, transport  # noqa: E402


async def _close(c, sid):
    if sid:
        await c.call_tool("apply_operations", {
            "session_id": sid, "ops": [{"op": "close_session"}], "confirmed": True})


async def core(c) -> Report:
    """Envelope shape, inspect metrics, undo/redo bookkeeping."""
    r = Report("core")
    env = (await c.call_tool("apply_operations", {"ops": [
        {"op": "create_sprite", "width": 32, "height": 32},
        {"op": "draw_rect", "x": 4, "y": 4, "width": 24, "height": 24,
         "color": "#E74C3C", "filled": True},
        {"op": "draw_pixel", "x": 16, "y": 6, "color": "#FFFFFF"},
    ]})).structured_content or {}
    sid = env.get("session_id")
    r.check("create batch ok", env.get("ok") is True, brief(env))
    r.check("envelope carries the promised fields",
            all(f in env for f in ENVELOPE_FIELDS), sorted(set(ENVELOPE_FIELDS) - set(env)))
    r.equal("fresh session has nothing to undo", (env.get("undo") or {}).get("available"), False)

    sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 2})).structured_content or {}
    m = metrics_of(sc)
    r.check("inspect sees both colors", m.get("color_count", 0) >= 2, m.get("color_count"))
    r.check("bbox covers the rect", (m.get("bbox") or {}).get("width", 0) >= 24, m.get("bbox"))
    r.check("coverage is sane", 0 < m.get("coverage", 0) <= 1, m.get("coverage"))

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "draw_rect", "x": 0, "y": 0, "width": 8, "height": 8,
         "color": "#29ADFF", "filled": True}]})).structured_content or {}
    r.check("second batch ok", env.get("ok") is True, brief(env))
    r.equal("undo now available", (env.get("undo") or {}).get("available"), True)

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [{"op": "undo"}]})).structured_content or {}
    r.check("undo ok", env.get("ok") is True, brief(env))
    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [{"op": "redo"}]})).structured_content or {}
    r.check("redo ok", env.get("ok") is True, brief(env))

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [{"op": "undo"}, {"op": "undo"}]})).structured_content or {}
    r.check("undo past the beginning is reported, not silently ignored", env.get("ok") is False,
            brief(env))
    await _close(c, sid)
    return r


async def codegen(c) -> Report:
    """atomic=true is all-or-nothing; atomic=false honours what worked."""
    r = Report("codegen / partial success")
    env = (await c.call_tool("apply_operations", {"ops": [
        {"op": "create_sprite", "width": 16, "height": 16},
        {"op": "draw_rect", "x": 2, "y": 2, "width": 12, "height": 12,
         "color": "#29ADFF", "filled": True},
    ]})).structured_content or {}
    sid = env.get("session_id")
    r.check("atomic batch ok", env.get("ok") is True, brief(env))

    env = (await c.call_tool("apply_operations", {"session_id": sid, "atomic": False, "ops": [
        {"op": "draw_pixel", "x": 0, "y": 0, "color": "#FF0000"},
        {"op": "draw_pixel", "x": 5, "y": 5, "color": "#00FF00", "layer": 9},
        {"op": "draw_pixel", "x": 15, "y": 15, "color": "#FF00FF"},
    ]})).structured_content or {}
    warns = env.get("warnings") or []
    r.check("atomic=false reports ok", env.get("ok") is True, brief(env))
    r.check("atomic=false warns 'partial success'", any("partial success" in w for w in warns), warns)
    r.check("atomic=false names the failing op",
            any("op 2 failed" in w for w in warns), warns)

    sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 1})).structured_content or {}
    colors = set(metrics_of(sc).get("palette") or [])
    r.check("the two surviving pixels are on the canvas",
            "#FF0000" in colors and "#FF00FF" in colors, sorted(colors))
    await _close(c, sid)
    return r


async def atomic_rollback(c) -> Report:
    """A failing atomic batch must leave the canvas exactly as it was."""
    r = Report("atomic rollback")
    env = (await c.call_tool("apply_operations", {"ops": [
        {"op": "create_sprite", "width": 16, "height": 16},
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
    ]})).structured_content or {}
    sid = env.get("session_id")
    before = metrics_of((await c.call_tool(
        "inspect", {"session_id": sid, "scale": 1})).structured_content).get("coverage")

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "draw_pixel", "x": 3, "y": 3, "color": "#0000FF"},
        {"op": "draw_pixel", "x": 4, "y": 4, "color": "#0000FF", "layer": 9},
    ]})).structured_content or {}
    r.check("failed batch reports failure", env.get("ok") is False, brief(env))
    r.equal("failed batch points at the op", (env.get("error") or {}).get("op_index"), 1)

    after = metrics_of((await c.call_tool(
        "inspect", {"session_id": sid, "scale": 1})).structured_content).get("coverage")
    r.equal("canvas untouched after rollback", after, before)

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "draw_pixel", "x": 2, "y": 2, "color": "#00FF00"}]})).structured_content or {}
    r.check("session still usable after rollback", env.get("ok") is True, brief(env))
    await _close(c, sid)
    return r


async def bounds(c) -> Report:
    """Off-canvas drawing is rejected in Lua; Aseprite would silently drop it."""
    r = Report("bounds")
    env = (await c.call_tool("apply_operations", {
        "ops": [{"op": "create_sprite", "width": 16, "height": 16}]})).structured_content or {}
    sid = env.get("session_id")

    cases = (
        # label, op, one of the phrasings the Lua bounds check is allowed to use
        ("negative x", {"op": "draw_pixel", "x": -1, "y": 0, "color": "#FF0000"}, "outside"),
        ("past the edge", {"op": "draw_pixel", "x": 16, "y": 16, "color": "#FF0000"}, "outside"),
        ("overflowing rect", {"op": "draw_rect", "x": 14, "y": 14, "width": 10,
                              "height": 10, "color": "#29ADFF", "filled": True}, "does not fit"),
        ("fill outside", {"op": "fill_region", "x": 99, "y": 0, "color": "#29ADFF"}, "outside"),
    )
    for label, op, phrase in cases:
        env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [op]})).structured_content or {}
        r.check(f"{label} is rejected", env.get("ok") is False, brief(env))
        r.contains(f"{label} explains itself",
                   (env.get("error") or {}).get("message", ""), phrase)

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "draw_pixel", "x": 8, "y": 8, "color": "#00FF00"}]})).structured_content or {}
    r.check("valid pixel still draws", env.get("ok") is True, brief(env))
    sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 1})).structured_content or {}
    r.equal("exactly one color on canvas", metrics_of(sc).get("color_count"), 1)
    await _close(c, sid)
    return r


async def gates(c) -> Report:
    """Confirmation gates: destructive ops, paint_grid outside the work dir, run_lua."""
    r = Report("gates")
    from _harness import WORK

    env = (await c.call_tool("apply_operations", {
        "ops": [{"op": "create_sprite", "width": 16, "height": 16}]})).structured_content or {}
    sid = env.get("session_id")

    inside = WORK / "sessions" / str(sid) / "grid_ok.lua"
    inside.parent.mkdir(parents=True, exist_ok=True)
    inside.write_text('return { palette = { k = "#000000", r = "#E74C3C" }, rows = {\n'
                      '  "..kk..",\n  ".krrk.",\n  "krrrrk",\n  ".krrk.",\n'
                      '  "..kk..",\n} }\n', encoding="utf-8")
    outside = WORK.parent / "outside_grid.lua"      # outside the server work dir
    outside.write_text(inside.read_text(encoding="utf-8"), encoding="utf-8")

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "paint_grid", "path": str(inside)}]})).structured_content or {}
    r.check("grid inside the work dir needs no confirmation", env.get("ok") is True, brief(env))

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "paint_grid", "path": str(outside)}]})).structured_content or {}
    r.equal("grid outside the work dir is gated",
            (env.get("error") or {}).get("code"), "confirmation_required")

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "paint_grid", "path": str(outside)}], "confirmed": True})).structured_content or {}
    r.check("confirmed grid outside runs", env.get("ok") is True, brief(env))

    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "clear_canvas"}]})).structured_content or {}
    r.equal("destructive op is gated", (env.get("error") or {}).get("code"), "confirmation_required")

    env = (await c.call_tool("run_lua", {"session_id": sid, "code": "print(1)"})).structured_content or {}
    r.equal("run_lua needs unsafe", (env.get("error") or {}).get("code"), "unsafe_required")

    env = (await c.call_tool("run_lua", {"session_id": sid, "code": "print(1)",
                                         "unsafe": True})).structured_content or {}
    r.equal("run_lua needs confirmed too", (env.get("error") or {}).get("code"), "confirmation_required")

    outside.unlink(missing_ok=True)
    await _close(c, sid)
    return r


async def animation(c) -> Report:
    """Frames, durations and tags survive the round trip."""
    r = Report("animation")
    env = (await c.call_tool("apply_operations", {"ops": [
        {"op": "create_sprite", "width": 16, "height": 16},
        {"op": "draw_pixel", "x": 4, "y": 4, "color": "#FF0000", "frame": 1},
        {"op": "add_frames", "count": 3, "duration": 0.1},
        {"op": "draw_pixel", "x": 8, "y": 8, "color": "#00FF00", "frame": 4},
        {"op": "set_durations", "durations": [0.1, 0.2, 0.3, 0.4]},
        {"op": "add_tag", "name": "walk", "from_frame": 1, "to_frame": 4},
    ]})).structured_content or {}
    sid = env.get("session_id")
    r.check("build ok", env.get("ok") is True, brief(env))

    f1 = (await c.call_tool("inspect", {"session_id": sid, "scale": 1, "frame": 1})).structured_content or {}
    f4 = (await c.call_tool("inspect", {"session_id": sid, "scale": 1, "frame": 4})).structured_content or {}
    r.equal("four frames", (f1.get("meta") or {}).get("frames_total"), 4)
    r.equal("durations kept", [f["duration"] for f in f1["meta"]["frames"]],
            [0.1, 0.2, 0.3, 0.4])
    r.equal("tag kept", [t["name"] for t in f1["meta"]["tags"]], ["walk"])
    r.check("frames differ", set(metrics_of(f1).get("palette") or []) !=
            set(metrics_of(f4).get("palette") or []),
            (metrics_of(f1).get("palette"), metrics_of(f4).get("palette")))
    await _close(c, sid)
    return r


async def runlua(c) -> Report:
    """run_lua shares the file snapshot: a failing snippet rolls the document back."""
    r = Report("run_lua snapshot")
    env = (await c.call_tool("apply_operations", {
        "ops": [{"op": "create_sprite", "width": 16, "height": 16}]})).structured_content or {}
    sid = env.get("session_id")

    env = (await c.call_tool("run_lua", {
        "session_id": sid, "code": 'app.activeSprite:newFrame() error("boom")',
        "unsafe": True, "confirmed": True})).structured_content or {}
    r.check("failing snippet reports failure", env.get("ok") is False, brief(env))
    r.contains("failing snippet explains itself",
               (env.get("error") or {}).get("message", ""), "boom")
    sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 1})).structured_content or {}
    r.equal("document rolled back", (sc.get("meta") or {}).get("frames_total"), 1)

    env = (await c.call_tool("run_lua", {
        "session_id": sid, "code": 'app.activeSprite:newFrame() print("ok")',
        "unsafe": True, "confirmed": True})).structured_content or {}
    r.check("good snippet ok", env.get("ok") is True, brief(env))
    sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 1})).structured_content or {}
    r.equal("good snippet sticks", (sc.get("meta") or {}).get("frames_total"), 2)
    await _close(c, sid)
    return r


async def perf(c) -> Report:
    """The timings the review flagged: flood fill and inspect on big canvases.

    Budgets are deliberately loose - they exist to catch an order-of-magnitude
    regression (or a timeout), not to police a few hundred milliseconds.
    """
    r = Report("perf")
    budget = {"create_2048_s": 10, "inspect_2048_s": 15, "fill_2048_s": 15,
              "inspect_full_2048_s": 15, "create_4096_s": 25, "inspect_4096_s": 40}

    t0 = time.time()
    env = (await c.call_tool("apply_operations", {
        "ops": [{"op": "create_sprite", "width": 2048, "height": 2048}]})).structured_content or {}
    sid = env.get("session_id")
    r.check("create 2048 ok", env.get("ok") is True, brief(env))
    timings = {"create_2048_s": round(time.time() - t0, 2)}

    t0 = time.time()
    sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 1})).structured_content or {}
    timings["inspect_2048_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    env = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
        {"op": "fill_region", "x": 0, "y": 0, "color": "#E74C3C"}]})).structured_content or {}
    timings["fill_2048_s"] = round(time.time() - t0, 2)
    r.check("flood fill 2048 ok", env.get("ok") is True, brief(env))

    t0 = time.time()
    sc = (await c.call_tool("inspect", {"session_id": sid, "scale": 1})).structured_content or {}
    timings["inspect_full_2048_s"] = round(time.time() - t0, 2)
    r.equal("full canvas is fully covered", metrics_of(sc).get("coverage"), 1.0)

    t0 = time.time()
    env = (await c.call_tool("apply_operations", {
        "ops": [{"op": "create_sprite", "width": 4096, "height": 4096}]})).structured_content or {}
    big = env.get("session_id")
    timings["create_4096_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    env = (await c.call_tool("apply_operations", {"session_id": big, "ops": [
        {"op": "fill_region", "x": 0, "y": 0, "color": "#29ADFF"}]})).structured_content or {}
    timings["fill_4096_s"] = round(time.time() - t0, 2)
    r.check("flood fill 4096 ok", env.get("ok") is True, brief(env))

    t0 = time.time()
    sc = (await c.call_tool("inspect", {"session_id": big, "scale": 1})).structured_content or {}
    timings["inspect_4096_s"] = round(time.time() - t0, 2)

    for name, value in timings.items():
        limit = budget.get(name, 60)
        r.check(f"{name} = {value}s (< {limit}s)", value < limit, value)
    await _close(c, big)
    await _close(c, sid)
    return r


SCENARIOS = {
    "core": core,
    "codegen": codegen,
    "atomic_rollback": atomic_rollback,
    "bounds": bounds,
    "gates": gates,
    "animation": animation,
    "runlua": runlua,
    "perf": perf,
}


async def main() -> int:
    argv = sys.argv[1:]
    names = list(SCENARIOS) if "--all" in argv else [a for a in argv if not a.startswith("-")] or ["core"]
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        sys.exit(f"unknown scenario(s): {unknown}\navailable: {', '.join(SCENARIOS)}")

    reports = []
    async with _client() as c:
        for name in names:
            t0 = time.time()
            try:
                reports.append(await SCENARIOS[name](c))
            except Exception as exc:  # noqa: BLE001 - a broken scenario is a failure, not a crash
                bad = Report(name)
                bad.check("scenario ran", False, f"{type(exc).__name__}: {exc}")
                reports.append(bad)
            print(f"({name} took {round(time.time() - t0, 1)}s)")
    return finish(reports)


def _client():
    from fastmcp import Client
    return Client(transport())


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))