"""黏液吞噬怪 产出脚本：建会话 -> 一批 op（扩帧 + 20 帧像素 + 时长 + tag）-> inspect 质检 -> 逐像素校验 -> 打包。

用法（在仓库任意位置）：
  python demo/slime_devourer/generator/produce.py             # 全流程
  python demo/slime_devourer/generator/produce.py --preview   # 只出本地接触表，不启动 Aseprite
需要 ASEPRITE_PATH 指向可执行的 Aseprite（否则依赖自动探测）。

流程刻意只用 v2 工具面：
- create_sprite / add_frames / paint_grid / set_durations / add_tag / save_sprite 全在
  **一个 apply_operations 原子批量**里 = 一次 Aseprite 进程（20 帧各一个 paint_grid）；
- 网格文件写进会话工作目录，所以 paint_grid 免 confirmed=true（见 AGENTS.md 的门闩约定）；
- inspect 只读回读结构与逐帧指标（多帧文档它自己会压成单帧再导出，frame 参数选帧），
  美术质检就是照着它的 metrics 做的；
- run_lua 只用来导出（精灵表 + 逐帧 PNG）——工具面没有 export op，这是正当的逃逸舱用途。
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
BUILD = HERE / ".build"                      # 中间产物，已 gitignore
ROOT = HERE.parents[2]                       # 仓库根（server.py 所在处）

PHASES = len(mo.PHASES)
DIRS = mo.DIRS
FRAMES = len(DIRS) * PHASES
GIF_PREFIX = "slime_devourer_devour"
SHEET_NAME = "slime_devourer_spritesheet.png"
ASE_NAME = "slime_devourer_devour.ase"
GIF_SCALE = 4
PREVIEW_SCALE = 6

DUR = mo.frame_durations()                   # 20 帧的逐帧时长（秒），五个相位循环
TAGS = {d: (DIRS.index(d) * PHASES + 1, DIRS.index(d) * PHASES + PHASES) for d in DIRS}


def _expected(grid) -> Image.Image:
    """设计矩阵 -> PIL 期望图（'.' 透明，其余查调色板）。"""
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
        stale.unlink()          # 上一版脚本按 frame.png -> frameN.png 落盘，别混进来

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

        # 网格文件放进会话工作目录：paint_grid 因此免确认
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

        # ---------------- inspect：结构与指标（旧版这里的 run_lua PROBE 是绕 bug 的，已撤） ----------------
        seen = []
        for i in range(1, FRAMES + 1):
            res = (await c.call_tool("inspect", {"session_id": sid, "frame": i})).structured_content
            assert res["ok"], res["error"]
            seen.append((i, res["meta"], res["metrics"]))
        meta = seen[0][1]
        print(f"inspect: {meta['frames_total']} frames, "
              f"tags={[t['name'] for t in meta['tags']]}, "
              f"max {max(m['color_count'] for _, _, m in seen)} colors")

        # ---------------- 导出（run_lua 唯一的用途） ----------------
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
-- 多帧文档上直接 saveCopyAs 会写成 frame1.png..frameN.png 却拿不到确切文件名，
-- 所以每帧先拷一个临时单帧文档再删掉其余帧（与 grassland_q 的导出同一个写法）。
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


# ---------------------------------------------------------------- 质检与校验
def _mask(grid):
    return {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c != "."}


def qa(seen) -> list[str]:
    """照 inspect 的 metrics 做美术质检；返回缺陷清单（空 = 全绿）。"""
    bad = []
    for i, _meta, m in seen:
        d, p = DIRS[(i - 1) // PHASES], (i - 1) % PHASES
        if m["isolated_pixels"]:          # 黏液怪身上孤立像素 = 脏点
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: "
                       f"{m['isolated_pixels']} isolated pixels")
        if m["near_duplicate_colors"]:
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: near duplicate colors "
                       f"{m['near_duplicate_colors']}")
        if m["semi_transparent_pixels"]:
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: "
                       f"{m['semi_transparent_pixels']} semi-transparent pixels")
        b = m["bbox"]
        # 剪影不许贴画布边：贴上去的那一行描边等于被画布切掉，导出后就是缺角
        if (b["x"] < 1 or b["y"] < 1
                or b["x"] + b["width"] > mo.W - 1 or b["y"] + b["height"] > mo.H - 1):
            bad.append(f"frame {i} {d}/{mo.PHASES[p]}: bbox {b} touches the canvas edge")

    # 时长：回读值必须与逐帧设计一致，而且五个相位两两不同（GIF 要保住节奏）
    got = [f["duration"] for _, meta, _ in seen for f in meta["frames"]]
    for i, (want, real) in enumerate(zip(DUR, got), start=1):
        if abs(want - real) > 0.005:
            bad.append(f"frame {i} duration {real} != designed {want}")
    if len(set(round(x, 3) for x in DUR[:PHASES])) != PHASES:
        bad.append("the five phase durations are not pairwise distinct")

    def at(d, p):
        return seen[mo.frame_index(d, p) - 1][2]

    # 体积曲线：蓄力压扁 / 突进拉长 / 咬合收缩 / 吞咽鼓包
    # （吞咽允许比突进更高——那一口猎物把轮廓顶起来，所以拉长只对前四相比）
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

    # 方向自洽：right 的剪影是 left 的水平镜像（尺寸/面积相同、bbox 对称），
    # 明暗仍按固定左上算，所以不能要求整帧像素相等。
    for p in range(PHASES):
        L, R = _mask(mo.build("left", p)), _mask(mo.build("right", p))
        mirrored = {(mo.W - 1 - x, y) for x, y in L}
        ml, mr = at("left", p)["bbox"], at("right", p)["bbox"]
        if mirrored != R or ml["width"] != mr["width"] or ml["height"] != mr["height"]:
            bad.append(f"phase {mo.PHASES[p]}: right is not the mirrored silhouette of left")
        if ml["x"] + mr["x"] + mr["width"] != mo.W:
            bad.append(f"phase {mo.PHASES[p]}: mirrored bbox x is off {ml} / {mr}")
        # 正视与背视在同一相位不该差出一截宽度（背视的下颌顶角只允许 +1px 半径）
        fu, bu = at("down", p)["bbox"], at("up", p)["bbox"]
        if fu["width"] != bu["width"] or fu["height"] != bu["height"]:
            bad.append(f"phase {mo.PHASES[p]}: front {fu} and back {bu} silhouettes disagree")
    return bad


def verify() -> bool:
    """逐像素比对 Aseprite 落盘结果与 Python 侧的设计矩阵。"""
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


# ---------------------------------------------------------------- 打包
def _publish(save, dest: Path, *, attempts: int = 6, pause: float = 0.5):
    """先写临时文件再 os.replace 覆盖：目标 gif 可能正被看图工具占用。"""
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
    """四个方向各一条 GIF（保留逐帧时长）+ 精灵表 + .ase。"""
    for d in DIRS:
        cells = [Image.open(_frame_png(mo.frame_index(d, p))).convert("RGBA")
                 .resize((mo.W * GIF_SCALE, mo.H * GIF_SCALE), Image.NEAREST)
                 for p in range(PHASES)]
        dest = DEMO / f"{GIF_PREFIX}_{d}.gif"
        _save(cells[0], dest, save_all=True, append_images=cells[1:],
              duration=[int(x * 1000) for x in mo.PHASE_DUR], loop=0,
              optimize=True, disposal=2)
        saved = Image.open(dest)
        # GIF 编码器会合并完全相同的帧，逐帧时长也可能被量化：两条都要断言。
        durs = []
        for i in range(saved.n_frames):
            saved.seek(i)
            durs.append(saved.info.get("duration"))
        assert saved.n_frames == PHASES, \
            f"{dest.name} 只有 {saved.n_frames} 帧：帧被 GIF 编码器合并了"
        assert durs == [int(x * 1000) for x in mo.PHASE_DUR], \
            f"{dest.name} 的逐帧时长丢了：{durs}"
        print(" ", dest.name, saved.size, saved.n_frames, "frames", durs)

    _copy(BUILD / "monster_sheet.png", DEMO / SHEET_NAME)
    print(" ", SHEET_NAME, Image.open(DEMO / SHEET_NAME).size)
    _copy(BUILD / "monster.ase", DEMO / ASE_NAME)
    print(" ", ASE_NAME)


def preview(scale: int = PREVIEW_SCALE) -> Path:
    """本地接触表：4 行（方向）x 5 列（相位），不经过 Aseprite，调形用。"""
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
    """把 inspect 回读的 bbox/coverage 排成体积曲线表（四个方向 x 五个相位）。"""
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
