"""Knightling 产出脚本：建会话 -> run_lua 建结构 -> 像素批次 -> 逐帧校验 -> 打包 demo 素材。

用法（在仓库任意位置）：python demo/Knightling/generator/produce.py
需要 ASEPRITE_PATH 指向可执行的 Aseprite（否则依赖自动检测）。
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path

from PIL import Image

import knight as ch

HERE = Path(__file__).parent                 # demo/Knightling/generator
DEMO = HERE.parent                           # demo/Knightling
BUILD = HERE / ".build"
ROOT = HERE.parents[2]

GIF_PREFIX = "knight"
SHEET_NAME = "chibi_knight_spritesheet.png"
ASE_NAME = "chibi_knight_walk.ase"

FRAMES = len(ch.DIRS) * ch.FRAMES
TAGS = [f"walk_{d}" for d in ch.DIRS]
DUR = 0.12                                   # 行走循环每帧等长，秒（本机构建按秒解释）

STRUCTURE = f"""
local sprite = app.activeSprite
if not sprite then error("run_lua: no active sprite") end
while #sprite.frames < {FRAMES} do sprite:newFrame() end
for i = 2, #sprite.frames do
  local blank = Image(sprite.width, sprite.height, sprite.colorMode)
  for _, layer in ipairs(sprite.layers) do
    local cel = layer:cel(sprite.frames[i])
    if cel then cel.image = blank else sprite:newCel(layer, sprite.frames[i], blank) end
  end
end
for i, f in ipairs(sprite.frames) do f.duration = {DUR} end
local names = {{{", ".join('"%s"' % t for t in TAGS)}}}
for r = 1, #names do
  local t = sprite:newTag()
  t.name = names[r]
  t.fromFrame = sprite.frames[(r - 1) * {ch.FRAMES} + 1]
  t.toFrame = sprite.frames[r * {ch.FRAMES}]
end
print("STRUCT frames=" .. #sprite.frames .. " tags=" .. #sprite.tags)
"""

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

        r = (await c.call_tool("run_lua", {"session_id": sid, "code": STRUCTURE,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]
        print("structure:", r["op_results"][0]["data"]["stdout"].strip().splitlines()[-1])

        for d in ch.DIRS:
            ops = [o for i in range(ch.FRAMES)
                   for o in ch.ops_for(ch.build(d, i), ch.frame_index(d, i))]
            r = (await c.call_tool("apply_operations",
                                   {"session_id": sid, "ops": ops})).structured_content
            assert r["ok"], r["error"]
            print(f"  {d:6s} {len(ops):4d} ops  {r['timing_ms']}ms")

        r = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
            {"op": "save_sprite", "path": str(BUILD / "walk.ase")}]})).structured_content
        assert r["ok"], r["error"]

        r = (await c.call_tool("run_lua", {"session_id": sid, "code": EXPORT,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]

        # 逐帧 inspect：确认帧数与指标，且原文档没被 inspect 的删帧逻辑改动
        res = (await c.call_tool("inspect", {"session_id": sid, "frame": 1})).structured_content
        assert res["ok"], res["error"]
        print("inspect:", res["meta"]["frames_total"], "frames,",
              len(res["meta"]["tags"]), "tags")


def verify():
    bad = 0
    for d in ch.DIRS:
        for i in range(ch.FRAMES):
            n = ch.frame_index(d, i)
            got = Image.open(BUILD / "frames" / f"frame{n}.png").convert("RGBA")
            want = ch.build(d, i)
            for y in range(ch.H):
                for x in range(ch.W):
                    c = want[y][x]
                    r, g, b, a = got.getpixel((x, y))
                    ok = (a == 0) if c is None else (
                        a != 0 and "#%02X%02X%02X" % (r, g, b) == ch.P[c])
                    if not ok:
                        bad += 1
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
            f"{out.name} 只有 {saved.n_frames} 帧：有帧完全相同，被 GIF 编码器合并了"
        print(" ", out.name, saved.size, saved.n_frames, "frames")
    shutil.copyfile(BUILD / "sheet.png", DEMO / SHEET_NAME)
    shutil.copyfile(BUILD / "walk.ase", DEMO / ASE_NAME)
    print(" ", SHEET_NAME, Image.open(DEMO / SHEET_NAME).size)


def distinct_poses():
    """每方向 6 帧必须两两不同，否则 GIF 会静默合并相同帧。"""
    dupes = []
    for d in ch.DIRS:
        uniq = {tuple(map(tuple, ch.build(d, i))) for i in range(ch.FRAMES)}
        if len(uniq) != ch.FRAMES:
            dupes.append(f"{d}: {len(uniq)}/{ch.FRAMES} 唯一")
    return dupes


if __name__ == "__main__":
    dupes = distinct_poses()
    assert not dupes, "存在完全相同的帧 -> " + "; ".join(dupes)
    asyncio.run(produce())
    if verify():
        package()
