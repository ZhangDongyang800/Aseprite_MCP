"""Slime devourer build script: create session -> one batch of ops (frames + 20
frames of pixels + durations + tags) -> inspect QC -> per-pixel verification ->
package.

Usage (from anywhere in the repo):
  python demo/slime_devourer/generator/produce.py             # full pipeline
  python demo/slime_devourer/generator/produce.py --preview   # local contact sheet, no Aseprite
ASEPRITE_PATH must point at a runnable Aseprite (otherwise auto-detection is used).

The flow deliberately uses only the v2 tool surface:
- create_sprite / add_frames / paint_grid / set_durations / add_tag / save_sprite
  all live in **one atomic apply_operations batch** = one Aseprite process (one
  paint_grid per frame, 20 in total);
- the grid files go into the session working directory, so paint_grid needs no
  confirmed=true (see the gate convention in AGENTS.md);
- inspect only reads back the structure and per-frame metrics (for multi-frame
  documents it collapses to a single frame before exporting, and the frame param
  picks the frame); the art QC is built on its metrics;
- run_lua is used for export only (sprite sheet + per-frame PNGs) -- the tool
  surface has no export op, which is a legitimate use of the escape hatch.
"""

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

import monster as mo

HERE = Path(__file__).parent                 # demo/slime_devourer/generator
DEMO = HERE.parent                           # demo/slime_devourer
BUILD = HERE / ".build"                      # intermediate artifacts, gitignored
ROOT = HERE.parents[2]                       # repo root (where server.py lives)

PHASES = len(mo.PHASES)
DIRS = mo.DIRS
FRAMES = len(DIRS) * PHASES
GIF_PREFIX = "slime_devourer_devour"
SHEET_NAME = "slime_devourer_spritesheet.png"
ASE_NAME = "slime_devourer_devour.ase"
GIF_SCALE = 4
PREVIEW_SCALE = 6

DUR = mo.frame_durations()                   # per-frame durations (seconds), five phases cycling
TAGS = {d: (DIRS.index(d) * PHASES + 1, DIRS.index(d) * PHASES + PHASES) for d in DIRS}


def _expected(grid) -> Image.Image:
    """Design matrix -> expected PIL image ('.' is transparent, the rest looks up in
    the palette)."""
    img = Image.new("RGBA", (mo.W, mo.H), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, code in enumerate(row):
            if code != ".":
                r, g, b = (int(mo.PALETTE[code][i:i + 2], 16) for i in (1, 3, 5))
                img.putpixel((x, y), (r, g, b, 255))
    return img


def _frame_png(i: int) -> Path:
    return BUILD / "frames" / f"frame_{i}.png"


async def produce():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    (BUILD / "frames").mkdir(parents=True, exist_ok=True)
    for stale in (BUILD / "frames").glob("frame*.png"):
        stale.unlink()          # old script wrote frame.png -> frameN.png; drop them

    env = {**os.environ, "ASEPRITE_WORK_DIR": str(BUILD / "work"),
           "ASEPRITE_MCP_MODE": "cli"}
    transport = StdioTransport(command=sys.executable, args=["server.py"],
                               cwd=str(ROOT), env=env)

    async with Client(transport) as c:
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": mo.W, "height": mo.H,
             "color_mode": "rgb"}]})).structured_content
        assert r["ok"], r["error"]
        sid = r["session_id"]

        # Grid files go into the session working dir: paint_grid therefore needs
        # no confirmation.
        grids = []
        for d in DIRS:
            for p in range(PHASES):
                i = mo.frame_index(d, p)
                path = BUILD / "work" / "sessions" / sid / f"monster_{i:02d}.lua"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(mo.grid_lua(mo.build(d, p), f"{d}/{mo.PHASES[p]}"),
                                encoding="utf-8")
                grids.append(path)

        ops = [{"op": "add_frames", "count": FRAMES - 1, "duration": DUR[0]}]
        ops += [{"op": "paint_grid", "path": str(g), "frame": i + 1}
                for i, g in enumerate(grids)]
        ops += [{"op": "set_durations", "durations": DUR}]
        ops += [{"op": "add_tag", "name": f"devour_{d}", "from_frame": lo, "to_frame": hi}
                for d, (lo, hi) in TAGS.items()]
        ops.append({"op": "save_sprite", "path": str(BUILD / "monster.ase")})

        r = (await c.call_tool("apply_operations",
                               {"session_id": sid, "ops": ops})).structured_content
        assert r["ok"], r["error"]
        print(f"monster: {len(ops)} ops in one atomic batch, {r['timing_ms']}ms, "
              f"warnings={r['warnings'] or 'none'}")

        # ---------------- inspect: structure and metrics ----------------
        # (the old run_lua PROBE here worked around a bug and is gone)
        seen = []
        for i in range(1, FRAMES + 1):
            res = (await c.call_tool("inspect", {"session_id": sid, "frame": i})).structured_content
            assert res["ok"], res["error"]
            seen.append((i, res["meta"], res["metrics"]))
        meta = seen[0][1]
        print(f"inspect: {meta['frames_total']} frames, "
              f"tags={[t['name'] for t in meta['tags']]}, "
              f"max {max(m['color_count'] for _, _, m in seen)} colors")

        # ---------------- export (the only use of run_lua) ----------------
        export = f"""
local s = app.activeSprite
app.command.ExportSpriteSheet({{
  ui = false,
  type = SpriteSheetType.ROWS,
  columns = {PHASES},
  textureFilename = "{(BUILD / 'monster_sheet.png').as_posix()}",
  dataFilename = "{(BUILD / 'monster_data.json').as_posix()}",
  dataFormat = SpriteSheetDataFormat.JSON_HASH,
}})
-- On a multi-frame document saveCopyAs writes frame1.png..frameN.png and the exact name is not knowable,
-- so each frame is copied into a temporary single-frame document first - the same trick inspect.lua uses.
for i = 1, #s.frames do
  local copy = Sprite(s)
  for j = #copy.frames, 1, -1 do
    if j ~= i then copy:deleteFrame(copy.frames[j]) end
  end
  copy.frames[1].duration = 100
  copy:saveCopyAs("{(BUILD / 'frames' / 'frame').as_posix()}" .. "_" .. i .. ".png")
  copy:close()
end
print("EXPORT frames=" .. #s.frames)
"""
        r = (await c.call_tool("run_lua", {"session_id": sid, "code": export,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]
        print("export:", r["op_results"][0]["data"]["stdout"].strip().splitlines()[-1])

        await c.call_tool("apply_operations", {
            "session_id": sid, "ops": [{"op": "close_session"}], "confirmed": True})
    return seen


# ---------------------------------------------------------------- QC and verification
def _mask(grid):
    return {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c != "."}


def qa(seen) -> list[str]:
    """Art QC driven by inspect's metrics; returns the defect list (empty = all green)."""
    bad = []
    for i, _meta, m in seen:
        d, p = DIRS[(i - 1) // PHASES], (i - 1) % PHASES
        if m["isolated_pixels"]:          # an isolated pixel on a slime is a speck
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: "
                       f"{m['isolated_pixels']} isolated pixels")
        if m["near_duplicate_colors"]:
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: near duplicate colors "
                       f"{m['near_duplicate_colors']}")
        if m["semi_transparent_pixels"]:
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: "
                       f"{m['semi_transparent_pixels']} semi-transparent pixels")
        b = m["bbox"]
        # The silhouette may not hug the canvas edge: an outline on the edge is
        # clipped by the canvas, so the export loses a corner.
        if (b["x"] < 1 or b["y"] < 1
                or b["x"] + b["width"] > mo.W - 1 or b["y"] + b["height"] > mo.H - 1):
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: bbox {b} touches the canvas edge")

    # Durations: the read-back must match the per-frame design, and the five
    # phases must be pairwise distinct (the GIF must keep its rhythm).
    got = [f["duration"] for _, meta, _ in seen for f in meta["frames"]]
    for i, (want, real) in enumerate(zip(DUR, got), start=1):
        if abs(want - real) > 0.005:
            bad.append(f"frame {i} duration {real} != designed {want}")
    if len(set(round(x, 3) for x in DUR[:PHASES])) != PHASES:
        bad.append("the five phase durations are not pairwise distinct")

    def at(d, p):
        return seen[mo.frame_index(d, p) - 1][2]

    # Volume curve: windup squashes / lunge stretches / chomp contracts / swallow bulges
    # (swallow may be taller than the lunge -- that mouthful lifts the silhouette, so
    # the stretch check only compares the first four phases)
    for d in DIRS:
        curve = [at(d, p) for p in range(PHASES)]
        box = [m["bbox"] for m in curve]
        cov = [m["coverage"] for m in curve]
        height = [b["height"] for b in box]
        if height[1] >= height[0]:
            bad.append(f"{d}: windup is not squashed ({height[0]} -> {height[1]})")
        if not (height[2] == max(height[:4]) and cov[2] == max(cov)):
            bad.append(f"{d}: lunge is not the stretched/fullest phase "
                       f"{list(zip(height, [round(c, 3) for c in cov]))}")
        if not (height[3] < height[2] and cov[3] < cov[2]):
            bad.append(f"{d}: chomp does not contract after the lunge")
        if not (height[4] >= height[0] and cov[4] >= cov[0]):
            bad.append(f"{d}: swallow gains no bulk")

    # Direction consistency: right's silhouette is left mirrored horizontally (same
    # size/area, symmetric bbox), while shading still comes from a fixed upper left,
    # so whole-frame pixel equality cannot be required.
    for p in range(PHASES):
        L, R = _mask(mo.build("left", p)), _mask(mo.build("right", p))
        mirrored = {(mo.W - 1 - x, y) for x, y in L}
        ml, mr = at("left", p)["bbox"], at("right", p)["bbox"]
        if mirrored != R or ml["width"] != mr["width"] or ml["height"] != mr["height"]:
            bad.append(f"phase {mo.PHASES[p]}: right is not the mirrored silhouette of left")
        if ml["x"] + mr["x"] + mr["width"] != mo.W:
            bad.append(f"phase {mo.PHASES[p]}: mirrored bbox x is off {ml} / {mr}")
        # Front and back must not differ in width within a phase (the back jaw's
        # pushed-out corner is allowed only +1px of radius).
        fu, bu = at("down", p)["bbox"], at("up", p)["bbox"]
        if fu["width"] != bu["width"] or fu["height"] != bu["height"]:
            bad.append(f"phase {mo.PHASES[p]}: front {fu} and back {bu} silhouettes disagree")
    return bad


def verify() -> bool:
    """Pixel comparison of Aseprite's written output against the Python-side design
    matrix."""
    ok = True
    for d in DIRS:
        for p in range(PHASES):
            i = mo.frame_index(d, p)
            path = _frame_png(i)
            if not path.exists():
                print(f"  frame {i}: missing export")
                ok = False
                continue
            got = Image.open(path).convert("RGBA").tobytes()
            want = _expected(mo.build(d, p)).tobytes()
            diff = sum(1 for a, b in zip(got, want) if a != b) // 4
            print(f"  frame {i:2d} {d}/{mo.PHASES[p]:8s} {diff} px differ")
            ok = ok and diff == 0
    return ok


# ---------------------------------------------------------------- packaging
def _publish(save, dest: Path, *, attempts: int = 6, pause: float = 0.5):
    """Write a temp file first, then overwrite with os.replace: the target gif may
    be held open by an image viewer."""
    tmp = dest.with_name(f"{dest.stem}.part{dest.suffix}")
    for attempt in range(attempts):
        try:
            save(tmp)
            os.replace(tmp, dest)
            return
        except OSError:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            if attempt == attempts - 1:
                raise
            time.sleep(pause)


def _copy(src: Path, dest: Path):
    _publish(lambda tmp: shutil.copyfile(src, tmp), dest)


def _save(img, dest: Path, **kwargs):
    _publish(lambda tmp: img.save(tmp, **kwargs), dest)


def package():
    """One GIF per direction (keeping per-frame durations) + sprite sheet + .ase."""
    for d in DIRS:
        cells = [Image.open(_frame_png(mo.frame_index(d, p))).convert("RGBA")
                 .resize((mo.W * GIF_SCALE, mo.H * GIF_SCALE), Image.NEAREST)
                 for p in range(PHASES)]
        dest = DEMO / f"{GIF_PREFIX}_{d}.gif"
        _save(cells[0], dest, save_all=True, append_images=cells[1:],
              duration=[int(x * 1000) for x in mo.PHASE_DUR], loop=0,
              optimize=True, disposal=2)
        saved = Image.open(dest)
        # The GIF encoder merges identical frames and may quantize per-frame
        # durations: assert both.
        durs = []
        for i in range(saved.n_frames):
            saved.seek(i)
            durs.append(saved.info.get("duration"))
        assert saved.n_frames == PHASES, \
            f"{dest.name} has only {saved.n_frames} frames: frames were merged by the GIF encoder"
        assert durs == [int(x * 1000) for x in mo.PHASE_DUR], \
            f"{dest.name} lost its per-frame durations: {durs}"
        print(" ", dest.name, saved.size, saved.n_frames, "frames", durs)

    _copy(BUILD / "monster_sheet.png", DEMO / SHEET_NAME)
    print(" ", SHEET_NAME, Image.open(DEMO / SHEET_NAME).size)
    _copy(BUILD / "monster.ase", DEMO / ASE_NAME)
    print(" ", ASE_NAME)


def preview(scale: int = PREVIEW_SCALE) -> Path:
    """Local contact sheet: 4 rows (directions) x 5 columns (phases), without
    Aseprite, for shaping."""
    bg = (28, 30, 26)
    sheet = Image.new("RGB", (mo.W * scale * PHASES, mo.H * scale * len(DIRS)), bg)
    for r, d in enumerate(DIRS):
        for col in range(PHASES):
            img = _expected(mo.build(d, col)).resize((mo.W * scale, mo.H * scale),
                                                     Image.NEAREST)
            sheet.paste(img, (col * mo.W * scale, r * mo.H * scale), img)
    out = BUILD / "sheet_preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def _volume_table(seen):
    """Lay out inspect's read-back bbox/coverage as a volume-curve table (four
    directions x five phases)."""
    print("  phase       down(front)    left           right          up(back)")
    for p in range(PHASES):
        cells = []
        for d in DIRS:
            m = seen[mo.frame_index(d, p) - 1][2]
            b = m["bbox"]
            cells.append(f"{b['width']:2d}x{b['height']:2d}/{m['coverage']:.3f}")
        print(f"  {mo.PHASES[p]:8s} " + "  ".join(cells))


def main():
    if "--preview" in sys.argv:
        path = preview()
        print(path, Image.open(path).size)
        return 0
    seen = asyncio.run(produce())
    problems = qa(seen)
    for i, _, m in seen:
        b = m["bbox"]
        print(f"  frame {i:2d} iso={m['isolated_pixels']} colors={m['color_count']} "
              f"cov={m['coverage']:.3f} bbox={b['width']}x{b['height']}@{b['x']},{b['y']} "
              f"dupes={len(m['near_duplicate_colors'])}")
    _volume_table(seen)
    if problems:
        print("\nQA FAILED:")
        for line in problems:
            print("  -", line)
        raise SystemExit(1)
    print("QA: isolated=0, no near-duplicate colors, no edge clipping, "
          "durations per frame, mirror + front/back silhouettes consistent")
    if not verify():
        raise SystemExit("pixel check failed - see above")
    package()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
