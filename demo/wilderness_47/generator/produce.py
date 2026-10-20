"""Wilderness 47-blob tileset build script: create session -> one batch of ops to
draw everything -> per-pixel verification -> package the demo assets.

Usage (from anywhere in the repo):
    ASEPRITE_PATH=/path/to/aseprite.exe python demo/wilderness_47/generator/produce.py

Only the v2 tool surface is used:
- atlas = one `apply_operations` atomic batch: `add_frames` + 4x `paint_grid` (one
  per water phase) + `set_durations` + `add_tag` + `save_sprite`; scene = another
  batch of `paint_grid` + `save_sprite`;
- the grid files go into the **session working directory**, so `paint_grid` needs
  no `confirmed=true` (see the gate convention in AGENTS.md);
- `run_lua` is only used to export PNGs -- the tool surface has no export op. On a
  multi-frame document `saveCopyAs` writes `x1.png...xN.png`, so copy a temporary
  single-frame document first and export from that, the old `inspect.lua` trick.

Verification is not "no error reported": `verify()` compares the PNG Aseprite wrote
against the Python-side design matrix pixel by pixel, and also checks that the 4
water phases are pairwise distinct and that the 47-tile matrices appear in the
atlas without duplicates or gaps.
"""

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import tiles as tl

HERE = Path(__file__).parent                 # demo/wilderness_47/generator
DEMO = HERE.parent                           # demo/wilderness_47
BUILD = HERE / ".build"
ROOT = HERE.parents[2]

ATLAS_PNG = "wilderness_tileset.png"
PREVIEW_PNG = "wilderness_preview.png"
SCENE_PNG = "wilderness_scene.png"
GIF_NAME = "wilderness_water.gif"
ATLAS_ASE = "wilderness_tileset.ase"
SCENE_ASE = "wilderness_scene.ase"
MANIFEST = "wilderness_manifest.json"

FRAME_DUR = 0.14
# Sample cell for the water animation: row 16, slot 2 = water's interior variant A
WATER_CELL = (tl.VARIANT_ROW, tl.BLOCKS.index("water"))
SCENE_SCALE = 2


def _grid_file(sid, name, matrix, title):
    """Write the design matrix as the Lua data file paint_grid consumes, inside the
    session work dir (no confirmation needed)."""
    path = BUILD / "work" / "sessions" / sid / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tl.grid_lua(matrix, title), encoding="utf-8")
    return path


def _expected(matrix):
    img = Image.new("RGBA", (len(matrix[0]), len(matrix)), (0, 0, 0, 0))
    for y, row in enumerate(matrix):
        for x, code in enumerate(row):
            if code != ".":
                h = tl.PAL[code]
                img.putpixel((x, y), tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    return img


def _diff(got_path, matrix) -> int:
    got = Image.open(got_path).convert("RGBA")
    want = _expected(matrix)
    if got.size != want.size:
        return -1
    a, b = got.tobytes(), want.tobytes()
    return sum(1 for i in range(0, len(a), 4) if a[i:i + 4] != b[i:i + 4])


async def produce():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    env = {**os.environ, "ASEPRITE_WORK_DIR": str(BUILD / "work"),
           "ASEPRITE_MCP_MODE": "cli", "ASEPRITE_TIMEOUT": "180"}
    transport = StdioTransport(command=sys.executable, args=["server.py"],
                               env=env, cwd=str(ROOT))

    async with Client(transport) as c:
        # ---------------- atlas: 4 water phases = 4 frames ----------------
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": tl.SHEET_W, "height": tl.SHEET_H,
             "color_mode": "rgb"}]})).structured_content
        assert r["ok"], r["error"]
        atlas = r["session_id"]

        grids = [_grid_file(atlas, f"atlas_{p}.lua", tl.sheet_frame(p),
                           f"wilderness 47-blob atlas, water phase {p}")
                 for p in range(tl.WATER_PHASES)]

        ops = [{"op": "add_frames", "count": tl.WATER_PHASES - 1, "duration": FRAME_DUR}]
        ops += [{"op": "paint_grid", "path": str(g), "frame": i + 1}
                for i, g in enumerate(grids)]
        ops += [{"op": "set_durations", "durations": [FRAME_DUR] * tl.WATER_PHASES},
                {"op": "add_tag", "name": "water_loop", "from_frame": 1,
                 "to_frame": tl.WATER_PHASES},
                {"op": "save_sprite", "path": str(BUILD / ATLAS_ASE)}]
        r = (await c.call_tool("apply_operations",
                               {"session_id": atlas, "ops": ops})).structured_content
        assert r["ok"], r["error"]
        print(f"atlas: {tl.SHEET_W}x{tl.SHEET_H} x{tl.WATER_PHASES} frames, "
              f"{len(ops)} ops in one batch, {r['timing_ms']}ms, "
              f"warnings={r['warnings'] or 'none'}")

        (BUILD / "frames").mkdir(parents=True, exist_ok=True)
        await _export_frames(c, atlas, BUILD / "frames" / "atlas")

        res = (await c.call_tool("inspect", {"session_id": atlas, "frame": 1})).structured_content
        assert res["ok"], res["error"]
        print("inspect:", res["meta"]["frames_total"], "frames,",
              [t["name"] for t in res["meta"]["tags"]],
              f'{res["metrics"]["color_count"]} colors in frame 1')

        # ---------------- scene: lay the terrain map out via the blob table ----------------
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": tl.SCENE_COLS * tl.TILE,
             "height": tl.SCENE_ROWS * tl.TILE, "color_mode": "rgb"}]})).structured_content
        assert r["ok"], r["error"]
        scene = r["session_id"]

        scene_grid = _grid_file(scene, "scene.lua", tl.scene_frame(0),
                               "wilderness demo scene")
        r = (await c.call_tool("apply_operations", {"session_id": scene, "ops": [
            {"op": "paint_grid", "path": str(scene_grid)},
            {"op": "save_sprite", "path": str(BUILD / SCENE_ASE)},
        ]})).structured_content
        assert r["ok"], r["error"]
        print(f"scene: {tl.SCENE_COLS}x{tl.SCENE_ROWS} tiles, {r['timing_ms']}ms, "
              f"warnings={r['warnings'] or 'none'}")

        await _export_frames(c, scene, BUILD / "scene")

        for sid in (atlas, scene):
            await c.call_tool("apply_operations", {
                "session_id": sid, "ops": [{"op": "close_session"}], "confirmed": True})


async def _export_frames(c, sid, stem: Path):
    """Export PNGs frame by frame: on a multi-frame document saveCopyAs writes
    x1..xN, so copy to a temporary single-frame document first."""
    if stem.name == "scene":
        code = (f'app.activeSprite:saveCopyAs("{(stem.parent / "scene.png").as_posix()}")\n'
                'print("EXPORT scene")\n')
    else:
        code = f"""
local s = app.activeSprite
for i = 1, #s.frames do
  local copy = Sprite(s)
  for j = #copy.frames, 1, -1 do
    if j ~= i then copy:deleteFrame(copy.frames[j]) end
  end
  copy.frames[1].duration = 100
  copy:saveCopyAs("{stem.as_posix()}" .. "_" .. i .. ".png")
  copy:close()
end
print("EXPORT frames=" .. #s.frames)
"""
    r = (await c.call_tool("run_lua", {"session_id": sid, "code": code,
                                       "unsafe": True,
                                       "confirmed": True})).structured_content
    assert r["ok"], r["error"]
    print("export:", r["op_results"][0]["data"]["stdout"].strip().splitlines()[-1])


def verify():
    """Pixel-compare Aseprite's output with the design matrix; also check the
    matrices themselves for completeness."""
    bad = 0
    for phase in range(tl.WATER_PHASES):
        d = _diff(BUILD / "frames" / f"atlas_{phase + 1}.png", tl.sheet_frame(phase))
        bad += max(d, 0)
        print(f"  atlas phase {phase + 1}: {d} px differ")
    d = _diff(BUILD / "scene.png", tl.scene_frame(0))
    bad += max(d, 0)
    print(f"  scene: {d} px differ")

    hashes = {Image.open(BUILD / "frames" / f"atlas_{i + 1}.png").tobytes()
              for i in range(tl.WATER_PHASES)}
    if len(hashes) != tl.WATER_PHASES:
        print(f"  FAIL: only {len(hashes)}/{tl.WATER_PHASES} water phases differ")
        return False

    # The 4 47-tile matrices in the atlas must be complete and unique: sorted into
    # the first 47 slots of each block by ascending mask.
    for bi, block in enumerate(tl.BLOCKS):
        seen = {(slot["row"], slot["col"]) for slot in tl.manifest()["slots"]
                if slot["block"] == block and slot["bits"] is not None}
        if len(seen) != 47:
            print(f"  FAIL: block {block} landed only {len(seen)} mask slots")
            return False
    if bad:
        return False
    print(f"pixel check: green ({tl.WATER_PHASES} atlas frames + scene, 0 pixels differ)")
    return True


def _preview():
    """Annotated image for humans and the README: 2x + separators + slot number,
    block name and bitmask."""
    scale, gap, label = 2, 4, 12
    cell = tl.TILE * scale
    w = tl.COLS * (cell + gap) + gap
    h = tl.ROWS * (cell + label + gap) + gap
    sheet = Image.open(BUILD / "frames" / "atlas_1.png").convert("RGBA")
    out = Image.new("RGBA", (w, h), (26, 28, 34, 255))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.load_default()
    except OSError:                                    # pragma: no cover
        font = None
    slots = tl.manifest()["slots"]
    for row in range(tl.ROWS):
        for col in range(tl.COLS):
            idx = row * tl.COLS + col
            slot = next((s for s in slots if s["index"] == idx), None)
            if slot is None:
                continue
            cx = gap + col * (cell + gap)
            cy = gap + row * (cell + label + gap)
            tile = sheet.crop((col * tl.TILE, row * tl.TILE,
                               (col + 1) * tl.TILE, (row + 1) * tl.TILE))
            out.alpha_composite(tile.resize((cell, cell), Image.NEAREST), (cx, cy))
            draw.rectangle([cx - 1, cy - 1, cx + cell, cy + cell + label],
                           outline=(84, 90, 104, 255))
            tag = slot["hex"] if slot["bits"] is not None else slot.get("name", slot["block"])
            draw.text((cx + 1, cy + cell + 1), f"{idx} {slot['block'][:5]} {tag}",
                      fill=(206, 214, 228, 255), font=font)
    return out


def _publish(save, dest: Path, *, attempts=6, pause=0.5):
    """Write a temp file first, then overwrite with os.replace: the target may be
    held open by an image viewer (Windows).

    The temp name keeps the real suffix, because PIL decides the format from the
    extension.
    """
    tmp = dest.with_name(f"{dest.stem}.part{dest.suffix}")
    for attempt in range(attempts):
        try:
            save(tmp)
            os.replace(tmp, dest)
            return
        except OSError:
            tmp.unlink(missing_ok=True)
            if attempt == attempts - 1:
                raise
            time.sleep(pause)


def _cell(img, row, col, scale=4):
    return img.crop((col * tl.TILE, row * tl.TILE,
                     (col + 1) * tl.TILE, (row + 1) * tl.TILE)).resize(
        (tl.TILE * scale, tl.TILE * scale), Image.NEAREST)


def package():
    _publish(lambda t: shutil.copyfile(BUILD / "frames" / "atlas_1.png", t),
             DEMO / ATLAS_PNG)
    print(" ", ATLAS_PNG, Image.open(DEMO / ATLAS_PNG).size)

    _publish(lambda t: _preview().save(t), DEMO / PREVIEW_PNG)
    print(" ", PREVIEW_PNG, Image.open(DEMO / PREVIEW_PNG).size)

    scene = Image.open(BUILD / "scene.png").convert("RGBA")
    _publish(lambda t: scene.resize((scene.width * SCENE_SCALE, scene.height * SCENE_SCALE),
                                    Image.NEAREST).save(t), DEMO / SCENE_PNG)
    print(" ", SCENE_PNG, f"{scene.size} -> {SCENE_SCALE}x")

    cells = [_cell(Image.open(BUILD / "frames" / f"atlas_{p + 1}.png").convert("RGBA"),
                   *WATER_CELL) for p in range(tl.WATER_PHASES)]
    out = DEMO / GIF_NAME
    _publish(lambda t: cells[0].save(t, save_all=True, append_images=cells[1:],
                                     duration=[int(FRAME_DUR * 1000)] * tl.WATER_PHASES,
                                     loop=0, optimize=True, disposal=2), out)
    saved = Image.open(out)
    assert saved.n_frames == tl.WATER_PHASES, \
        f"{out.name} has only {saved.n_frames} frames: frames were merged by the GIF encoder"
    print(" ", GIF_NAME, saved.size, saved.n_frames, "frames")

    _publish(lambda t: t.write_text(json.dumps(tl.manifest(), ensure_ascii=False,
                                               indent=1), encoding="utf-8"),
             DEMO / MANIFEST)
    print(" ", MANIFEST, len(tl.manifest()["slots"]), "slots")

    for name in (ATLAS_ASE, SCENE_ASE):
        _publish(lambda t, s=name: shutil.copyfile(BUILD / s, t), DEMO / name)
        print(" ", name)


if __name__ == "__main__":
    probs = tl.selfcheck()
    assert not probs, "design selfcheck failed: " + "; ".join(probs)
    BUILD.mkdir(parents=True, exist_ok=True)
    asyncio.run(produce())
    if verify():
        package()
    else:
        raise SystemExit("pixel check failed - see above")
