"""修帧时长（本机构建里 Frame.duration 单位是秒）+ 逐帧像素比对 Aseprite 落盘结果。"""

import asyncio
import os
import sys
from pathlib import Path

from PIL import Image

import monster as mo

HERE = Path(__file__).parent          # demo/slime_devourer/generator
BUILD = HERE / ".build"
ROOT = HERE.parents[2]                # 仓库根
DUR_S = [0.2, 0.1, 0.08, 0.09, 0.22]  # idle/蓄力/突进/咬合/吞咽，秒

FIX = """
local s = app.activeSprite
local dur = {DUR}
for i, f in ipairs(s.frames) do f.duration = dur[((i - 1) % 5) + 1] end
local out = {}
for i, f in ipairs(s.frames) do out[#out + 1] = f.duration end
print("dur=" .. table.concat(out, ","))
""".replace("{DUR}", "{" + ", ".join(str(d) for d in DUR_S) + "}")

REEXPORT = f"""
local s = app.activeSprite
s:saveCopyAs("{(BUILD / 'frames' / 'frame.png').as_posix()}")
print("reexport ok")
"""


async def main():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    # Aseprite 路径交给服务器按 ASEPRITE_PATH / PATH / 常见安装位置自动检测
    env = {**os.environ, "ASEPRITE_WORK_DIR": str(BUILD / "work"),
           "ASEPRITE_MCP_MODE": "cli"}
    transport = StdioTransport(command=sys.executable, args=["server.py"],
                               env=env, cwd=str(ROOT))
    async with Client(transport) as c:
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "open_sprite", "path": str(BUILD / "monster.ase")}]})).structured_content
        assert r["ok"], r["error"]
        sid = r["session_id"]
        print("reopened", sid, r["op_results"])

        r = (await c.call_tool("run_lua", {"session_id": sid, "code": FIX,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]
        print(r["op_results"][0]["data"]["stdout"].strip().splitlines()[-1])

        r = (await c.call_tool("apply_operations", {"session_id": sid, "ops": [
            {"op": "save_sprite", "path": str(BUILD / "monster.ase")}]})).structured_content
        assert r["ok"], r["error"]
        print("saved back:", r["op_results"][0]["data"]["path"])

        r = (await c.call_tool("run_lua", {"session_id": sid, "code": REEXPORT,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]

    bad = 0
    for d in mo.DIRS:
        for p in range(len(mo.PHASES)):
            i = mo.frame_index(d, p)
            got = Image.open(BUILD / "frames" / f"frame{i}.png").convert("RGBA")
            want = mo.build(d, p)
            diff = []
            for y in range(mo.H):
                for x in range(mo.W):
                    ch = want[y][x]
                    r, g, b, a = got.getpixel((x, y))
                    if ch == ".":
                        if a != 0:
                            diff.append((x, y, "transparent", (r, g, b, a)))
                    elif a == 0 or "#%02X%02X%02X" % (r, g, b) != mo.PALETTE[ch]:
                        diff.append((x, y, ch, (r, g, b, a)))
            if diff:
                bad += 1
                print(f"frame {i} ({d}/{mo.PHASES[p]}) {len(diff)} px differ, e.g. {diff[:3]}")
    print("pixel-exact frames:", 20 - bad, "/ 20")


asyncio.run(main())
