"""Knightling 产出脚本：建会话 -> 一次原子批量（结构 + 24 帧 paint_grid）-> inspect 质检 -> 逐像素校验 -> 打包。

用法（在仓库任意位置）：python demo/Knightling/generator/produce.py
需要 ASEPRITE_PATH 指向可执行的 Aseprite（否则依赖自动探测）。
工作目录刻意放在 .build/ 下并且是纯 ASCII 路径：Aseprite 对非 ASCII 路径会报误导性的
"lua 引擎缺失"，而这里的一切中间产物都不该跑到仓库的 work/ 里去。

流程只用 v2 工具面：
- create_sprite / add_frames / paint_grid / set_durations / add_tag / save_sprite 全部走
  apply_operations，24 帧的完整动画（结构 + 像素）是一个原子批量 = 一次 Aseprite 进程；
- 每帧一个 paint_grid，网格文件写在**会话工作目录里**，所以免 confirmed=true；
- inspect 逐帧读 metrics 做美术质检（孤立像素 / 近似色 / 脚底基线 / 左右体积对称）；
- export op 负责精灵表与逐帧 PNG，run_lua 不再参与这条产出链。
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
DUR = 0.12                                   # 行走循环每帧等长（set_durations 的单位是秒）
FOOT = 28                                    # 脚底基线：24 帧都必须落在这一行

def _fail(report, message):
    report.append(message)


def _isolated_px(png_path):
    """孤立像素的坐标（与 src/v2/inspect.py 的 _isolated 同一判据：四邻皆空）。

    只在指标报非 0 时才跑，用来把"哪颗像素"说出来。
    """
    alpha = Image.open(png_path).convert("RGBA").getchannel("A")
    return [(x, y) for y in range(ch.H) for x in range(ch.W)
            if alpha.getpixel((x, y))
            and all(alpha.getpixel((x + dx, y + dy)) == 0
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= x + dx < ch.W and 0 <= y + dy < ch.H)]


async def produce():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    (BUILD / "frames").mkdir(parents=True, exist_ok=True)
    for stale in (BUILD / "frames").glob("frame*.png"):
        stale.unlink()                       # 绝不让校验吃到上一次的旧导出
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

        # 网格文件放进会话工作目录：paint_grid 因此不需要 confirmed=true
        grids = []
        for d in ch.DIRS:
            for i in range(ch.FRAMES):
                n = ch.frame_index(d, i)
                path = BUILD / "work" / "sessions" / sid / f"frame{n:02d}.lua"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(ch.grid_lua(d, i), encoding="utf-8")
                grids.append((d, i, n, path))

        ops = [{"op": "add_frames", "count": FRAMES - 1, "duration": DUR}]
        ops += [{"op": "paint_grid", "path": str(path), "frame": n}
                for _, _, n, path in grids]
        ops += [{"op": "set_durations", "durations": [DUR] * FRAMES}]
        ops += [{"op": "add_tag", "name": tag, "from_frame": k * ch.FRAMES + 1,
                 "to_frame": (k + 1) * ch.FRAMES} for k, tag in enumerate(TAGS)]
        ops += [{"op": "save_sprite", "path": str(BUILD / "walk.ase")}]

        r = (await c.call_tool("apply_operations",
                               {"session_id": sid, "ops": ops})).structured_content
        assert r["ok"], r["error"]
        print(f"batch: {len(ops)} ops in one atomic batch, {r['timing_ms']}ms, "
              f"warnings={r.get('warnings') or 'none'}")

        r = (await c.call_tool("apply_operations", {
            "session_id": sid,
            "ops": [
                {"op": "export", "format": "sheet",
                 "output": str(BUILD / "sheet.png"),
                 "layout": "rows", "columns": ch.FRAMES},
                {"op": "export", "format": "frames",
                 "output": str(BUILD / "frames" / "frame.png")},
            ],
        })).structured_content
        assert r["ok"], r["error"]
        print(f"export: {len(r['artifacts'])} artifacts, changed={r['changed']}")
        missing = [f"frame{n}.png" for n in range(1, FRAMES + 1)
                   if not (BUILD / "frames" / f"frame{n}.png").exists()]
        assert not missing and (BUILD / "sheet.png").exists(), \
            f"导出缺文件：{missing or 'sheet.png'}"

        await quality(c, sid, grids)

        await c.call_tool("apply_operations", {"session_id": sid,
                                               "ops": [{"op": "close_session"}],
                                               "confirmed": True})


async def quality(c, sid, grids):
    """逐帧 inspect 做美术质检；任何一条不达标都记进 failures 并在末尾炸掉。"""
    failures = []
    counts = {}
    tags = []
    durations = []
    print("\ninspect  frame  iso  colors  dup  cov    bbox(x,y,w,h)      foot  opaque")
    for d, i, n, _ in grids:
        res = (await c.call_tool("inspect", {"session_id": sid, "frame": n,
                                             "scale": 1})).structured_content
        assert res["ok"], res["error"]
        m = res["metrics"]
        tags = [t["name"] for t in res["meta"]["tags"]]
        durations = [round(f["duration"], 3) for f in res["meta"]["frames"]]
        if len(res["meta"]["frames"]) != FRAMES:
            _fail(failures, f"frame {n}: {len(res['meta']['frames'])} frames in the document")
        if m["isolated_pixels"]:
            pos = _isolated_px(BUILD / "frames" / f"frame{n}.png")
            _fail(failures, f"{d} frame {i + 1}: {m['isolated_pixels']} isolated pixels "
                            + ", ".join(f"{x},{y}='{ch.build(d, i)[y][x] or '?'}'"
                                        for x, y in pos))
        if m["near_duplicate_colors"]:
            _fail(failures, f"{d} frame {i + 1}: near-duplicate colors "
                            + ", ".join("/".join(pair) for pair in m["near_duplicate_colors"]))
        if m["semi_transparent_pixels"]:
            _fail(failures, f"{d} frame {i + 1}: {m['semi_transparent_pixels']} "
                            "semi-transparent pixels")
        if m["color_count"] > len(ch.P):
            _fail(failures, f"{d} frame {i + 1}: {m['color_count']} colors "
                            f"(palette has {len(ch.P)})")

        bbox = m["bbox"]
        foot = bbox["y"] + bbox["height"] - 1
        if foot != FOOT:
            _fail(failures, f"{d} frame {i + 1}: foot baseline drifted to row {foot}, "
                            f"expected {FOOT}")
        opaque = int(round(m["coverage"] * ch.W * ch.H))
        want = ch.opaque_count(d, i)
        counts[(d, i)] = opaque
        if opaque != want:
            _fail(failures, f"{d} frame {i + 1}: {opaque} opaque px drawn, model has {want}")

        print(f"{'':8s}{n:>4}  {m['isolated_pixels']:>3}  {m['color_count']:>6}  "
              f"{len(m['near_duplicate_colors']):>3}  {m['coverage']:.3f}  "
              f"({bbox['x']},{bbox['y']},{bbox['width']},{bbox['height']})  "
              f"{foot:>4}  {opaque:>4}/{want}")

    for i in range(ch.FRAMES):                    # 左右两向必须等体积（造型是镜像的）
        left, right = counts[("left", i)], counts[("right", i)]
        if left != right:
            _fail(failures, f"frame {i + 1}: left {left} px vs right {right} px - "
                            "侧向体积不对称")
    print(f"{'':8s}left/right volume per frame: "
          + ", ".join(f"{counts[('left', i)]}={counts[('right', i)]}"
                      for i in range(ch.FRAMES)))

    # set_durations 之后 24 帧必须等长（行走循环没有节奏变化）
    if len(set(durations)) != 1:
        _fail(failures, f"frame durations are not uniform: {sorted(set(durations))}")

    if sorted(tags) != sorted(TAGS):
        _fail(failures, f"tags are {tags}, expected {sorted(TAGS)}")

    if failures:
        for line in failures:
            print("  FAIL:", line)
        raise SystemExit(f"quality check failed: {len(failures)} problem(s)")
    print(f"quality: {FRAMES}/{FRAMES} frames clean (0 isolated px, 0 near-duplicate "
          f"colors, foot row {FOOT} on every frame, {durations[0]}s/frame, tags={tags})")


def _diff(got_path, grid) -> int:
    """导出图 vs 设计网格的像素差（直接比 RGBA 字节）。"""
    img = Image.open(got_path).convert("RGBA")
    if img.size != (ch.W, ch.H):
        return -1
    want = Image.new("RGBA", (ch.W, ch.H), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c:
                hexcode = ch.P[c].lstrip("#")
                want.putpixel((x, y), tuple(int(hexcode[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
    a, b = img.tobytes(), want.tobytes()
    return sum(1 for p, q in zip(a, b) if p != q) // 4


def verify():
    """逐像素比对导出结果与 Python 侧的网格：不是"没报错"，而是"画出来的就是设计的"。"""
    bad = 0
    for d in ch.DIRS:
        for i in range(ch.FRAMES):
            n = ch.frame_index(d, i)
            diff = _diff(BUILD / "frames" / f"frame{n}.png", ch.build(d, i))
            bad += max(diff, 0)
            print(f"  {d} frame {i + 1} (#{n}): {diff} px differ")
    if bad == 0:
        print(f"pixel check: {FRAMES}/{FRAMES} frames exact, 0 px differ")
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
