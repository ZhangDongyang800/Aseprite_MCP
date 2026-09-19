"""一次性把 20 帧吞噬怪落到 Aseprite：建会话 -> run_lua 建结构 -> 4 批像素 -> 校验 -> 导出。"""

import asyncio
import json
import os
import sys
from pathlib import Path

import monster as mo

HERE = Path(__file__).parent          # demo/slime_devourer/generator
BUILD = HERE / ".build"               # 中间产物，已 gitignore
ROOT = HERE.parents[2]                # 仓库根（server.py 所在处）
FRAMES = len(mo.DIRS) * len(mo.PHASES)

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
local dur = {{0.2, 0.1, 0.08, 0.09, 0.22}}  -- 本机 Frame.duration 单位是秒
for i, f in ipairs(sprite.frames) do f.duration = dur[((i - 1) % 5) + 1] end
local names = {{"devour_down", "devour_left", "devour_right", "devour_up"}}
for r = 1, 4 do
  local t = sprite:newTag()
  t.name = names[r]
  t.fromFrame = sprite.frames[(r - 1) * 5 + 1]
  t.toFrame = sprite.frames[r * 5]
end
print("STRUCT frames=" .. #sprite.frames .. " tags=" .. #sprite.tags)
"""

EXPORT = f"""
local sprite = app.activeSprite
if not sprite then error("run_lua: no active sprite") end
app.command.ExportSpriteSheet({{
  ui = false,
  type = SpriteSheetType.ROWS,
  columns = 5,
  textureFilename = "{(BUILD / 'monster_sheet.png').as_posix()}",
  dataFilename = "{(BUILD / 'monster_data.json').as_posix()}",
  dataFormat = SpriteSheetDataFormat.JSON_HASH,
}})
-- 多帧文档上 saveCopyAs 会自动逐帧写成 frame1.png..frameN.png（inspect 就是栽在这条行为上）
sprite:saveCopyAs("{(BUILD / 'frames' / 'frame.png').as_posix()}")
print("SHEET ok")
"""

PROBE = """
local s = app.activeSprite
local out = { "frames=" .. #s.frames, "tags=" .. #s.tags }
for i, t in ipairs(s.tags) do
  out[#out + 1] = string.format("%s:%d-%d", t.name, t.fromFrame.frameNumber, t.toFrame.frameNumber)
end
local durs = {}
for i, f in ipairs(s.frames) do durs[#durs + 1] = f.duration end
out[#out + 1] = "dur=" .. table.concat(durs, ",")
print(table.concat(out, " | "))
"""


async def main():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    (BUILD / "frames").mkdir(parents=True, exist_ok=True)
    # Aseprite 路径交给服务器按 ASEPRITE_PATH / PATH / 常见安装位置自动检测
    env = {**os.environ, "ASEPRITE_WORK_DIR": str(BUILD / "work"),
           "ASEPRITE_MCP_MODE": "cli"}
    transport = StdioTransport(command=sys.executable, args=["server.py"],
                               env=env, cwd=str(ROOT))
    async with Client(transport) as c:
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": mo.W, "height": mo.H,
             "color_mode": "rgb"}]})).structured_content
        assert r["ok"], r["error"]
        sid = r["session_id"]
        print("session", sid)

        r = (await c.call_tool("run_lua", {"session_id": sid, "code": STRUCTURE,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]
        print("structure:", r["op_results"][0]["data"]["stdout"].strip().splitlines()[-1])

        for d in mo.DIRS:
            ops = []
            for p in range(len(mo.PHASES)):
                ops += mo.ops_for(mo.build(d, p), mo.frame_index(d, p))
            r = (await c.call_tool("apply_operations",
                                   {"session_id": sid, "ops": ops})).structured_content
            print(f"{d:6s} {len(ops):4d} ops ok={r['ok']} {r.get('timing_ms')}ms")
            assert r["ok"], r["error"]

        # inspect 对多帧文档会抛 FileNotFoundError（见 README 反馈），这里用 run_lua 读结构
        r = (await c.call_tool("run_lua", {"session_id": sid, "code": PROBE,
                                           "unsafe": True, "confirmed": True})).structured_content
        print("probe:", r["op_results"][0]["data"]["stdout"].strip().splitlines()[-1])

        r = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
            {"op": "save_sprite", "path": str(BUILD / "monster.ase")}]})).structured_content
        print("save ok:", r["ok"], r["op_results"])

        r = (await c.call_tool("run_lua", {"session_id": sid, "code": EXPORT,
                                           "unsafe": True, "confirmed": True})).structured_content
        print("export ok:", r["ok"], r.get("error") or "")
        for f in ("monster_sheet.png", "monster_data.json", "monster.ase"):
            p = BUILD / f
            print("  ", f, p.exists(), p.stat().st_size if p.exists() else "-")
        print("   per-frame png:", len(list((BUILD / "frames").glob("frame*.png"))))


asyncio.run(main())
