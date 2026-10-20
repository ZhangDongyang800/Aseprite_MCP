"""Dark reaper build script: create session -> draw all 24 frames in one atomic
batch -> per-frame QC -> per-pixel verification -> package.

Usage (from anywhere in the repo): python demo/dark_reaper/generator/produce.py
ASEPRITE_PATH must point at a runnable Aseprite (otherwise auto-detection is used).

The flow deliberately uses only the v2 tool surface:
- `create_sprite` / `add_frames` / 24x `paint_grid` / `set_durations` / 4x
  `add_tag` / `save_sprite` form one atomic batch = one Aseprite process (the old
  version used run_lua with hand-written Lua to build the structure + 4616
  draw_rect calls in 4 batches, so drawing this set of frames took 7 processes);
- the grid files go into the **session working directory**, so `paint_grid` needs
  no `confirmed=true` (the gate convention in AGENTS.md);
- `run_lua` is kept for export only: the tool surface has no export op, which is a
  legitimate use of the escape hatch;
- `inspect` does the per-frame art QC (isolated pixels / near-duplicate colours /
  bbox bottom edge / whether the red eyes got covered); if the metrics miss, the
  run fails right there and never reaches packaging.
"""

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

import reaper as ch

HERE = Path(__file__).parent                 # demo/dark_reaper/generator
DEMO = HERE.parent                           # demo/dark_reaper
BUILD = HERE / ".build"
ROOT = HERE.parents[2]

GIF_PREFIX = "dark_reaper"
SHEET_NAME = "dark_reaper_spritesheet.png"
ASE_NAME = "dark_reaper_walk.ase"

FRAMES = len(ch.DIRS) * ch.FRAMES
TAGS = [f"walk_{d}" for d in ch.DIRS]
DUR = 0.12                                   # equal frame length across the loop, in seconds
EYE = ch.P["R"]                              # glowing red eyes under the hood; 'up' is the back
GROUND = 30                                  # heel row + outline: every bbox bottom equals it

EXPORT = f"""
local s = app.activeSprite
app.command.ExportSpriteSheet({{
  ui = false,
  type = SpriteSheetType.ROWS,
  columns = {ch.FRAMES},
  textureFilename = "{(BUILD / 'sheet.png').as_posix()}",
  dataFilename = "{(BUILD / 'sheet.json').as_posix()}",
  dataFormat = SpriteSheetDataFormat.JSON_HASH,
}})
-- On a multi-frame document saveCopyAs does not write frame.png but frame1.png .. frame24.png; per-frame verification reads exactly those
s:saveCopyAs("{(BUILD / 'frames' / 'frame.png').as_posix()}")
print("EXPORT ok")
"""


async def produce():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    (BUILD / "frames").mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ASEPRITE_WORK_DIR": str(BUILD / "work"),
           "ASEPRITE_MCP_MODE": "cli"}
    transport = StdioTransport(command=sys.executable, args=["server.py"],
                               env=env, cwd=str(ROOT))
    async with Client(transport) as c:
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": ch.W, "height": ch.H,
             "color_mode": "rgb"}]})).structured_content
        assert r["ok"], r["error"]
        sid = r["session_id"]

        # One grid file per frame, inside the session work dir -> paint_grid needs
        # no confirmation.
        grids = []
        for d in ch.DIRS:
            for i in range(ch.FRAMES):
                n = ch.frame_index(d, i)
                path = BUILD / "work" / "sessions" / sid / f"reaper_{n:02d}.lua"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(ch.grid_lua(ch.build(d, i), f"dark reaper {d} {i + 1}"),
                                encoding="utf-8")
                grids.append((n, path))

        ops = [{"op": "add_frames", "count": FRAMES - 1, "duration": DUR}]
        ops += [{"op": "paint_grid", "path": str(path), "frame": n} for n, path in grids]
        ops += [{"op": "set_durations", "durations": [DUR] * FRAMES}]
        ops += [{"op": "add_tag", "name": tag, "from_frame": r_ * ch.FRAMES + 1,
                 "to_frame": (r_ + 1) * ch.FRAMES}
                for r_, tag in enumerate(TAGS)]
        ops += [{"op": "save_sprite", "path": str(BUILD / "walk.ase")}]
        r = (await c.call_tool("apply_operations",
                               {"session_id": sid, "ops": ops})).structured_content
        assert r["ok"], r["error"]
        print(f"{len(ops)} ops in one atomic batch, {r['timing_ms']}ms, "
              f"warnings={r['warnings'] or 'none'}")

        r = (await c.call_tool("run_lua", {"session_id": sid, "code": EXPORT,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]

        await quality_check(c, sid)


async def quality_check(client, sid):
    """Per-frame inspect: turn art defects into assertions that fail the run, not
    just "no error reported"."""
    started = time.perf_counter()
    print("  frame  iso  colors  dupes  coverage  bbox(x,y,w,h)      bottom  eyes")
    bad = []
    for d in ch.DIRS:
        for i in range(ch.FRAMES):
            n = ch.frame_index(d, i)
            res = (await client.call_tool("inspect", {"session_id": sid,
                                                      "frame": n})).structured_content
            assert res["ok"], res["error"]
            meta, m = res["meta"], res["metrics"]
            # Document level: inspect's frame deletion only touches a temp copy;
            # the original must keep every frame.
            if meta["frames_total"] != FRAMES or [t["name"] for t in meta["tags"]] != TAGS:
                raise SystemExit(f"frame {n}: document changed under us -> {meta}")
            x, y = m["bbox"]["x"], m["bbox"]["y"]
            w, h = m["bbox"]["width"], m["bbox"]["height"]
            eyes = EYE in m["palette"]
            has_eyes = d != "up"                       # 'up' is the back, no face
            isolated = m["isolated_pixels"]
            dupes = len(m["near_duplicate_colors"])
            print(f"  {n:>5}  {isolated:>3}  {m['color_count']:>6}  {dupes:>5}  "
                  f"{m['coverage']:>8.3f}  ({x:>2},{y:>2},{w:>2},{h:>2}){'':>5}"
                  f"  {y + h:>6}  {'yes' if eyes else 'no'}")
            if isolated:
                bad.append(f"frame {n}: {isolated} isolated pixels (noise / broken outline)")
            if dupes:
                bad.append(f"frame {n}: near-duplicate colors {m['near_duplicate_colors']}")
            if y + h != GROUND:
                off = (y + h) - GROUND
                bad.append(f"frame {n}: bbox bottom {y + h} vs ground line {GROUND} "
                           f"({'+' if off > 0 else ''}{off})")
            if eyes != has_eyes:
                bad.append(f"frame {n} ({d}): red eyes {'covered' if not eyes else 'leaked'}")
    if bad:
        raise SystemExit("art QC failed:\n  " + "\n  ".join(bad))
    print(f"art QC: {FRAMES}/{FRAMES} frames clean "
          f"(0 isolated, 0 near-duplicate, bottom on the ground line, eyes where they belong) "
          f"in {time.perf_counter() - started:.1f}s")


def _diff(got_path: Path, grid) -> int:
    """Pixel difference between an exported frame and the Python-side design grid."""
    got = Image.open(got_path).convert("RGBA")
    bad = 0
    for y in range(ch.H):
        for x in range(ch.W):
            c = grid[y][x]
            r, g, b, a = got.getpixel((x, y))
            ok = (a == 0) if c is None else (
                a != 0 and "#%02X%02X%02X" % (r, g, b) == ch.P[c])
            bad += not ok
    return bad


def verify():
    """Per-frame pixel comparison: not "no error", but "what was drawn is what was
    designed"."""
    bad = 0
    for d in ch.DIRS:
        for i in range(ch.FRAMES):
            n = ch.frame_index(d, i)
            diff = _diff(BUILD / "frames" / f"frame{n}.png", ch.build(d, i))
            bad += diff
            if diff:
                print(f"  {d} frame {i + 1}: {diff} px differ")
    if bad == 0:
        print(f"pixel check: {FRAMES}/{FRAMES} frames exact")
    else:
        print(f"pixel check FAILED: {bad} px differ")
    return bad == 0


def package():
    scale = 4
    for d in ch.DIRS:
        cells = [Image.open(BUILD / "frames" / f"frame{ch.frame_index(d, i)}.png")
                 .convert("RGBA").resize((ch.W * scale, ch.H * scale), Image.NEAREST)
                 for i in range(ch.FRAMES)]
        out = DEMO / f"{GIF_PREFIX}_walk_{d}.gif"
        cells[0].save(out, save_all=True, append_images=cells[1:],
                      duration=[int(DUR * 1000)] * ch.FRAMES, loop=0,
                      optimize=True, disposal=2)
        saved = Image.open(out)
        assert saved.n_frames == ch.FRAMES, \
            f"{out.name} has only {saved.n_frames} frames: identical frames were merged by the GIF encoder"
        print(" ", out.name, saved.size, saved.n_frames, "frames")
    shutil.copyfile(BUILD / "sheet.png", DEMO / SHEET_NAME)
    shutil.copyfile(BUILD / "walk.ase", DEMO / ASE_NAME)
    print(" ", SHEET_NAME, Image.open(DEMO / SHEET_NAME).size)


def distinct_poses():
    """The 6 frames per direction must all differ, or the GIF silently merges
    identical frames."""
    dupes = []
    for d in ch.DIRS:
        uniq = {tuple(map(tuple, ch.build(d, i))) for i in range(ch.FRAMES)}
        if len(uniq) != ch.FRAMES:
            dupes.append(f"{d}: {len(uniq)}/{ch.FRAMES} unique")
    return dupes


if __name__ == "__main__":
    dupes = distinct_poses()
    assert not dupes, "some frames are identical -> " + "; ".join(dupes)
    asyncio.run(produce())
    if verify():
        package()
    else:
        raise SystemExit("pixel check failed - see above")
