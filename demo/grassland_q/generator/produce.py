"""Q版草原 tileset 产出脚本：建会话 -> 一批 ops 画完 -> 逐像素校验 -> 打包 demo 素材。

用法（在仓库任意位置）：python demo/grassland_q/generator/produce.py
需要 ASEPRITE_PATH 指向可执行的 Aseprite（否则依赖自动探测）。

流程刻意只用 v2 工具面：
- create_sprite / add_frames / paint_grid / set_durations / add_tag / save_sprite 走
  apply_operations，整个图集（含 4 帧水面动画）是一个原子批量 = 一次 Aseprite 进程；
- 网格文件写在**会话工作目录里**，所以 paint_grid 不需要 confirmed=true（见 AGENTS.md 的门闩约定）；
- run_lua 只用来导出 PNG（工具面没有 export op），属于正当的逃逸舱用途。
"""

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

import grassland_q as gl

HERE = Path(__file__).parent                 # demo/grassland_q/generator
DEMO = HERE.parent                           # demo/grassland_q
BUILD = HERE / ".build"
ROOT = HERE.parents[2]

SHEET_PNG = "grassland_q_tileset.png"
PREVIEW_PNG = "grassland_q_preview.png"
SCENE_PNG = "grassland_q_scene.png"
GIF_NAME = "grassland_q_water.gif"
SHEET_ASE = "grassland_q_tileset.ase"
SCENE_ASE = "grassland_q_scene.ase"

SHEET_W = gl.SHEET_COLS * gl.TILE
SHEET_H = gl.SHEET_ROWS * gl.TILE
SCENE_W = gl.SCENE_COLS * gl.TILE
SCENE_H = gl.SCENE_ROWS * gl.TILE
FRAME_DUR = 0.12
WATER_CELL = gl.TILE_NAMES.index("water")   # 水面瓦片在图集里的槽位（0 起）


def _expected(matrix):
    """矩阵 -> PIL 期望图（'.' 透明，其余查调色板）。"""
    img = Image.new("RGBA", (len(matrix[0]), len(matrix)), (0, 0, 0, 0))
    for y, row in enumerate(matrix):
        for x, code in enumerate(row):
            if code != ".":
                r, g, b = (int(gl.PAL[code][i:i + 2], 16) for i in (1, 3, 5))
                img.putpixel((x, y), (r, g, b, 255))
    return img


async def produce():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    env = {**os.environ, "ASEPRITE_WORK_DIR": str(BUILD / "work"),
           "ASEPRITE_MCP_MODE": "cli"}
    transport = StdioTransport(command=sys.executable, args=["server.py"],
                               env=env, cwd=str(ROOT))

    async with Client(transport) as c:
        # ---------------- 图集（4 帧，水面动画） ----------------
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": SHEET_W, "height": SHEET_H,
             "color_mode": "rgb"}]})).structured_content
        assert r["ok"], r["error"]
        sid = r["session_id"]

        # 网格文件放进会话工作目录：paint_grid 因此免确认
        grids = []
        for phase in range(gl.WATER_PHASES):
            path = BUILD / "work" / "sessions" / sid / f"sheet_{phase}.lua"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(gl.grid_lua(gl.sheet_frame(phase), f"tileset frame {phase}"),
                            encoding="utf-8")
            grids.append(path)

        ops = [{"op": "add_frames", "count": gl.WATER_PHASES - 1, "duration": FRAME_DUR}]
        ops += [{"op": "paint_grid", "path": str(g), "frame": i + 1}
                for i, g in enumerate(grids)]
        ops += [
            {"op": "set_durations", "durations": [FRAME_DUR] * gl.WATER_PHASES},
            {"op": "add_tag", "name": "water_loop", "from_frame": 1,
             "to_frame": gl.WATER_PHASES},
            {"op": "save_sprite", "path": str(BUILD / SHEET_ASE)},
        ]
        r = (await c.call_tool("apply_operations",
                               {"session_id": sid, "ops": ops})).structured_content
        assert r["ok"], r["error"]
        print(f"tileset: {len(ops)} ops in one batch, {r['timing_ms']}ms, "
              f"warnings={r['warnings'] or 'none'}")

        (BUILD / "frames").mkdir(parents=True, exist_ok=True)
        export_sheet = f"""
local s = app.activeSprite
for i = 1, #s.frames do
  local copy = Sprite(s)
  for j = #copy.frames, 1, -1 do
    if j ~= i then copy:deleteFrame(copy.frames[j]) end
  end
  copy.frames[1].duration = 100
  copy:saveCopyAs("{(BUILD / 'frames' / 'sheet').as_posix()}" .. "_" .. i .. ".png")
  copy:close()
end
print("EXPORT frames=" .. #s.frames)
"""
        r = (await c.call_tool("run_lua", {"session_id": sid, "code": export_sheet,
                                           "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]
        print("export:", r["op_results"][0]["data"]["stdout"].strip().splitlines()[-1])

        res = (await c.call_tool("inspect", {"session_id": sid, "frame": 1})).structured_content
        assert res["ok"], res["error"]
        print("inspect:", res["meta"]["frames_total"], "frames,",
              [t["name"] for t in res["meta"]["tags"]],
              f'{res["metrics"]["color_count"]} colors')

        # ---------------- 场景（瓦片拼装） ----------------
        r = (await c.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": SCENE_W, "height": SCENE_H,
             "color_mode": "rgb"}]})).structured_content
        assert r["ok"], r["error"]
        sid2 = r["session_id"]
        scene_grid = BUILD / "work" / "sessions" / sid2 / "scene.lua"
        scene_grid.parent.mkdir(parents=True, exist_ok=True)
        scene_grid.write_text(gl.grid_lua(gl.scene(), "grassland-q scene"), encoding="utf-8")

        r = (await c.call_tool("apply_operations", {"session_id": sid2, "ops": [
            {"op": "paint_grid", "path": str(scene_grid)},
            {"op": "save_sprite", "path": str(BUILD / SCENE_ASE)},
        ]})).structured_content
        assert r["ok"], r["error"]
        print(f"scene: {SCENE_W}x{SCENE_H}, {r['timing_ms']}ms")

        r = (await c.call_tool("run_lua", {"session_id": sid2, "code": f"""
app.activeSprite:saveCopyAs("{(BUILD / 'scene.png').as_posix()}")
print("EXPORT scene")
""", "unsafe": True, "confirmed": True})).structured_content
        assert r["ok"], r["error"]

        for target in (sid, sid2):
            await c.call_tool("apply_operations", {
                "session_id": target, "ops": [{"op": "close_session"}],
                "confirmed": True})


def _diff(got_path, matrix) -> int:
    """导出图 vs 设计矩阵的像素差（直接比 RGBA 字节，避免 getdata 的弃用告警）。"""
    got = Image.open(got_path).convert("RGBA").tobytes()
    want = _expected(matrix).tobytes()
    if len(got) != len(want):
        return -1
    return sum(1 for a, b in zip(got, want) if a != b) // 4


def verify():
    """逐像素比对导出结果与 Python 侧的设计矩阵：不是"没报错"，而是"画出来的就是设计的"。"""
    bad = 0
    for phase in range(gl.WATER_PHASES):
        diff = _diff(BUILD / "frames" / f"sheet_{phase + 1}.png", gl.sheet_frame(phase))
        bad += max(diff, 0)
        print(f"  sheet frame {phase + 1}: {diff} px differ")
    diff = _diff(BUILD / "scene.png", gl.scene())
    bad += max(diff, 0)
    print(f"  scene: {diff} px differ")

    # 水面四帧必须两两不同，否则 GIF 编码器会把相同帧合并掉
    hashes = {Image.open(BUILD / "frames" / f"sheet_{i + 1}.png").tobytes()
              for i in range(gl.WATER_PHASES)}
    if len(hashes) != gl.WATER_PHASES:
        print(f"  FAIL: water frames not distinct ({len(hashes)}/{gl.WATER_PHASES})")
        return False
    return bad == 0


def _preview():
    """给人和 README 看的标注图：4x 放大 + 分隔线 + 瓦片名。"""
    scale, gap, label_h = 4, 6, 10
    cell = gl.TILE * scale
    w = gl.SHEET_COLS * cell + (gl.SHEET_COLS + 1) * gap
    h = gl.SHEET_ROWS * (cell + label_h) + gap
    sheet = Image.open(BUILD / "frames" / "sheet_1.png").convert("RGBA")
    out = Image.new("RGBA", (w, h), (28, 30, 36, 255))
    draw = ImageDraw.Draw(out)
    for idx, name in enumerate(gl.TILE_NAMES):
        cx = gap + (idx % gl.SHEET_COLS) * (cell + gap)
        cy = gap + (idx // gl.SHEET_COLS) * (cell + label_h)
        tile = sheet.crop(((idx % gl.SHEET_COLS) * gl.TILE,
                           (idx // gl.SHEET_COLS) * gl.TILE,
                           (idx % gl.SHEET_COLS + 1) * gl.TILE,
                           (idx // gl.SHEET_COLS + 1) * gl.TILE))
        tile = tile.resize((cell, cell), Image.NEAREST)
        out.alpha_composite(tile, (cx, cy))
        draw.rectangle([cx - 1, cy - 1, cx + cell, cy + cell], outline=(90, 96, 110, 255))
        draw.text((cx + 1, cy + cell + 1), f"{idx}:{name}", fill=(214, 220, 232, 255))
    return out


def _publish(save, dest: Path, *, attempts: int = 6, pause: float = 0.5):
    """先写临时文件再 os.replace 覆盖目标。

    Windows 上目标文件可能正被看图工具 / 编辑器占用，直接 open(dest, "w+b") 会抛
    OSError。临时文件 + 原子替换顺带避免"写一半"的半成品，重试几次即可覆盖瞬时占用。
    """
    # 临时名必须保留真实后缀：PIL 靠扩展名判定格式
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
    _copy(BUILD / "frames" / "sheet_1.png", DEMO / SHEET_PNG)
    print(" ", SHEET_PNG, Image.open(DEMO / SHEET_PNG).size)

    _save(_preview(), DEMO / PREVIEW_PNG)
    print(" ", PREVIEW_PNG, Image.open(DEMO / PREVIEW_PNG).size)

    scene = Image.open(BUILD / "scene.png").convert("RGBA")
    _save(scene.resize((scene.width * 2, scene.height * 2), Image.NEAREST), DEMO / SCENE_PNG)
    print(" ", SCENE_PNG, f"{scene.size} -> 2x")

    cx = (WATER_CELL % gl.SHEET_COLS) * gl.TILE
    cy = (WATER_CELL // gl.SHEET_COLS) * gl.TILE
    cells = []
    for i in range(gl.WATER_PHASES):
        frame = Image.open(BUILD / "frames" / f"sheet_{i + 1}.png").convert("RGBA")
        cells.append(frame.crop((cx, cy, cx + gl.TILE, cy + gl.TILE))
                     .resize((gl.TILE * 4, gl.TILE * 4), Image.NEAREST))
    out = DEMO / GIF_NAME
    _save(cells[0], out, save_all=True, append_images=cells[1:],
          duration=[int(FRAME_DUR * 1000)] * gl.WATER_PHASES, loop=0,
          optimize=True, disposal=2)
    saved = Image.open(out)
    assert saved.n_frames == gl.WATER_PHASES, \
        f"{out.name} 只有 {saved.n_frames} 帧：帧被 GIF 编码器合并了"
    print(" ", GIF_NAME, saved.size, saved.n_frames, "frames")

    _copy(BUILD / SHEET_ASE, DEMO / SHEET_ASE)
    _copy(BUILD / SCENE_ASE, DEMO / SCENE_ASE)


if __name__ == "__main__":
    asyncio.run(produce())
    if verify():
        package()
    else:
        raise SystemExit("pixel check failed - see above")