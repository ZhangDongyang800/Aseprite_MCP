"""吞噬怪参数化生成器：4 方向 x 5 帧 @ 32x32，黏液软体怪。

侧视用"颅骨 + 下颚两块椭圆绕嘴角铰点反向旋转"的模型：张嘴时上颚抬起、
下颚落下，中间的楔形就是口腔。这样嘴是咬穿轮廓的缺口，而不是体内的一个洞。
几何只产出语义 mask，明暗与描边在渲染阶段统一算，所以 right 只是 left 的
mask 水平镜像，光照仍固定在左上。

  python monster.py            # 打印 20 帧 ASCII
  python monster.py --emit     # 生成 monster_ops.json
"""

import json
import math
import sys
from pathlib import Path

W = H = 32
DIRS = ["down", "left", "right", "up"]
PHASES = ["idle", "windup", "lunge", "chomp", "swallow"]

PALETTE = {
    "H": "#9BE564",  # 受光
    "M": "#5FBF3A",  # 主体黏液
    "D": "#3E8C26",  # 暗部
    "X": "#1F4D14",  # 描边
    "P": "#43152C",  # 口腔深处
    "Q": "#8E2F52",  # 舌
    "T": "#F4F7E4",  # 牙
    "t": "#BFC4A6",  # 牙尖暗部
    "E": "#101A0B",  # 眼
    "W": "#F6FFE8",  # 眼神光
}

GRID = [[None] * W for _ in range(H)]


def inb(x, y):
    return 0 <= x < W and 0 <= y < H


def put(x, y, c, overwrite=False):
    if inb(x, y) and (overwrite or GRID[y][x] is None):
        GRID[y][x] = c


def neighbors(cells):
    return {(x + dx, y + dy) for x, y in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (-1, 1), (1, -1), (-1, -1))}


def blob(cx, cy, rx, ry, n=2.2):
    return {(x, y) for y in range(H) for x in range(W)
            if (abs(x + 0.5 - cx) / rx) ** n + (abs(y + 0.5 - cy) / ry) ** n <= 1.0}


def rotate_pt(x, y, deg, pivot):
    """屏幕坐标（y 向下）下绕 pivot 转 deg；deg>0 让左侧前端上扬。"""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    px, py = pivot
    dx, dy = x - px, y - py
    return px + dx * ca - dy * sa, py + dx * sa + dy * ca


def ell_rot(cx, cy, rx, ry, deg, pivot, n=2.2):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    px, py = pivot
    out = set()
    for y in range(H):
        for x in range(W):
            dx, dy = x + 0.5 - px, y + 0.5 - py
            ox = px + dx * ca + dy * sa
            oy = py - dx * sa + dy * ca
            if (abs(ox - cx) / rx) ** n + (abs(oy - cy) / ry) ** n <= 1.0:
                out.add((x, y))
    return out


def tri(a, b, c):
    xs = [p[0] for p in (a, b, c)]
    ys = [p[1] for p in (a, b, c)]
    out = set()
    for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
        for x in range(int(min(xs)) - 1, int(max(xs)) + 2):
            px, py = x + 0.5, y + 0.5

            def sign(p1, p2):
                (x1, y1), (x2, y2) = p1, p2
                return (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)

            d1, d2, d3 = sign(a, b), sign(b, c), sign(c, a)
            if not (min(d1, d2, d3) < -1e-9 and max(d1, d2, d3) > 1e-9):
                out.add((x, y))
    return out


def flip(cells):
    return {(W - 1 - x, y) for x, y in cells}


# 侧视：面向左。u/d = 上下颚张角，lean = 整体前冲位移，pivot = 嘴角铰点
# gape = 张口半高（像素），0 即闭合成一条缝；u/d 让颅骨与下颚随之翻转
SIDE_CFG = {
    0: dict(u=3, d=2, gape=0.0, lean=(0, 0), pivot=(23, 16), skull=(16, 12, 9.6, 7.2),
            jaw=(15, 20.5, 10.2, 8.0)),
    1: dict(u=9, d=6, gape=2.4, lean=(2, 1), pivot=(23, 16), skull=(16, 12.5, 10.0, 6.6),
            jaw=(15, 21, 10.8, 7.6)),
    2: dict(u=17, d=12, gape=6.0, lean=(-3, -1), pivot=(23, 16), skull=(16, 11.5, 9.6, 7.0),
            jaw=(15, 20.5, 10.0, 8.2)),
    3: dict(u=5, d=4, gape=1.2, lean=(-1, 1), pivot=(23, 16), skull=(16, 12.5, 9.8, 6.8),
            jaw=(15, 21, 10.6, 7.6)),
    4: dict(u=7, d=5, gape=2.0, lean=(1, -1), pivot=(23, 16), skull=(16, 11, 9.2, 7.6),
            jaw=(15, 20, 9.8, 8.4)),
}

# 正视：头/身两块对称叶，mouth 为口腔椭圆半轴
FRONT_CFG = {
    0: dict(lean=(0, 0), head=(16, 12, 8.6, 6.6), body=(16, 21, 10.4, 8.0), mx=5.2, my=0.9),
    1: dict(lean=(0, 1), head=(16, 12.5, 9.2, 6.0), body=(16, 21.5, 11.0, 7.4), mx=6.2, my=2.6),
    2: dict(lean=(0, -1), head=(16, 11.5, 8.8, 6.8), body=(16, 21, 10.0, 8.6), mx=6.6, my=4.4),
    3: dict(lean=(0, 1), head=(16, 12.5, 9.0, 6.2), body=(16, 21.5, 10.8, 7.6), mx=6.0, my=1.7),
    4: dict(lean=(0, -1), head=(16, 11, 8.2, 7.2), body=(16, 21, 9.6, 8.8), mx=4.6, my=2.0),
}


def side_masks(phase):
    cfg = SIDE_CFG[phase]
    px, py = cfg["pivot"]
    scx, scy, srx, sry = cfg["skull"]
    jcx, jcy, jrx, jry = cfg["jaw"]
    skull = ell_rot(scx, scy, srx, sry, cfg["u"], (px, py))
    jaw = ell_rot(jcx, jcy, jrx, jry, -cfg["d"], (px, py))
    mass = skull | jaw
    g = cfg["gape"]
    wedge = tri((px, py), (3.0, py - 1.0 - g), (3.0, py + 1.0 + g * 0.8))
    maw = wedge & mass
    body = mass - wedge
    tongue = {(x, y) for x, y in maw if y >= py + 1 and x <= px - 2}
    ex, ey = rotate_pt(scx - 2.5, scy - 1.0, cfg["u"], (px, py))
    eye = {(int(ex) + i, int(ey) + j) for i in (0, 1) for j in (0, 1)}
    bulge = blob(px - 4.0, py + 6.0, 3.8, 3.6, 3.6) & body if phase == 4 else set()
    return dict(body=shift(body, *cfg["lean"]), maw=shift(maw, *cfg["lean"]),
                tongue=shift(tongue, *cfg["lean"]), eye=shift(eye, *cfg["lean"]),
                bulge=shift(bulge, *cfg["lean"]), ridge=set(), seam=set(),
                skip=set())


def front_masks(phase):
    cfg = FRONT_CFG[phase]
    hx, hy, hrx, hry = cfg["head"]
    bx, by, brx, bry = cfg["body"]
    body = blob(hx, hy, hrx, hry) | blob(bx, by, brx, bry)
    mx, my = cfg["mx"], cfg["my"]
    maw = blob(bx, by - 3.0, mx, my, n=2.0) & body
    tongue = {(x, y) for x, y in maw
              if y >= by - 3.0 + my * 0.4 and abs(x - bx) <= mx * 0.5}
    eye = set()
    for ex in (int(round(hx - 4.6)), int(round(hx + 4.6))):
        if phase in (2, 3):
            eye |= {(ex - 1, int(hy) - 1), (ex, int(hy) - 1), (ex + 1, int(hy) - 1)}
        else:
            eye |= {(ex - 1, int(hy) - 2), (ex, int(hy) - 2),
                    (ex - 1, int(hy) - 1), (ex, int(hy) - 1)}
    bulge = blob(bx, by + 4.0, 4.6, 3.8, 3.8) & body if phase == 4 else set()
    return dict(body=shift(body, *cfg["lean"]), maw=shift(maw, *cfg["lean"]),
                tongue=shift(tongue, *cfg["lean"]), eye=shift(eye, *cfg["lean"]),
                bulge=shift(bulge, *cfg["lean"]), ridge=set(), seam=set(),
                skip=set())


def back_masks(phase):
    cfg = FRONT_CFG[phase]
    hx, hy, hrx, hry = cfg["head"]
    bx, by, brx, bry = cfg["body"]
    wide = 1.0 + 0.055 * cfg["mx"] if phase in (1, 2, 3) else 1.0
    hrx *= wide
    body = blob(hx, hy, hrx, hry) | blob(bx, by, brx, bry)
    top = int(hy - hry) + 2
    bot = int(by + bry) - 3
    seam = {(int(hx), y) for y in range(top, bot + 1)} & body
    ridge = neighbors(seam) & body
    # 从背后看，张开的下颌在头部两侧顶出暗角
    maw = set()
    if phase in (1, 2, 3):
        k = 1 + int(cfg["mx"] * 0.35)
        edge_l, edge_r = int(hx - hrx) + 1, int(hx + hrx) - 1
        for y in range(int(hy) + 1, int(hy) + 1 + k * 2):
            maw |= {(edge_l, y), (edge_r, y)}
        maw &= body
    return dict(body=shift(body, *cfg["lean"]), maw=shift(maw, *cfg["lean"]),
                tongue=set(), eye=set(), bulge=set(), ridge=shift(ridge, *cfg["lean"]),
                seam=shift(seam, *cfg["lean"]), skip=set())


def teeth_of(maw):
    """上下牙交错，嘴角不放牙：否则牙会糊成一排噪点。"""
    cols = {}
    for x, y in maw:
        cols.setdefault(x, []).append(y)
    if not cols:
        return set()
    xs = sorted(cols)
    lo, hi = xs[0], xs[-1]
    out = set()
    for x in xs:
        if x - lo < (hi - lo) * 0.18 or hi - x < (hi - lo) * 0.10:
            continue
        top, bot = min(cols[x]), max(cols[x])
        if bot - top < 2:
            continue
        if (x - lo) % 3 == 1:
            out |= {(x, top), (x, top + 1)}
        elif (x - lo) % 3 == 2:
            out |= {(x, bot), (x, bot - 1)}
    return out


def render(m):
    for row in GRID:
        for i in range(W):
            row[i] = None
    body, maw = m["body"], m["maw"]
    cols = {}
    for x, y in maw:
        cols.setdefault(x, []).append(y)
    maxh = max((len(v) for v in cols.values()), default=0)
    open_jaw = maxh >= 3 or (m["phase"] == 3 and maxh >= 2)
    teeth = teeth_of(maw) if open_jaw else set()
    rim = (neighbors(maw) & body) - maw if open_jaw else set()

    for x, y in sorted(body, key=lambda p: (p[1], p[0])):
        if (x, y + 1) not in body or (x + 1, y) not in body or (x + 1, y + 1) not in body:
            put(x, y, "D")
        elif (x, y - 1) not in body and (x - 1, y) not in body:
            put(x, y, "H")
        else:
            put(x, y, "M")

    # 咽下的猎物：lump 本体回亮、外圈压暗、左上受光，才像皮下鼓起的一团
    bulge = m["bulge"]
    for x, y in bulge:
        put(x, y, "M", overwrite=True)
    for x, y in (neighbors(bulge) & body) - bulge:
        put(x, y, "D", overwrite=True)
    for x, y in bulge:
        if (x, y - 1) not in bulge and (x - 1, y) not in bulge:
            put(x, y, "H", overwrite=True)
    for x, y in m["ridge"]:
        put(x, y, "D", overwrite=True)
    for x, y in m["seam"]:
        put(x, y, "X", overwrite=True)
    for x, y in m["ridge"]:
        if x < int(W / 2):
            put(x - 1, y, "H", overwrite=True)

    for x, y in maw:
        put(x, y, "P" if open_jaw else "X", overwrite=True)
    if open_jaw:
        for x, y in m["tongue"]:
            put(x, y, "Q", overwrite=True)
        for x, y in rim - teeth:
            put(x, y, "X", overwrite=True)
        for x, y in teeth:
            put(x, y, "T", overwrite=True)
        for x, y in teeth:  # 单格牙尖压暗，避免整排死白
            if (x, y - 1) not in teeth and (x, y + 1) not in teeth:
                put(x, y, "t", overwrite=True)

    for x, y in m["eye"]:
        put(x, y, "E", overwrite=True)
    if m["eye"] and m["phase"] not in (2, 3):
        ex, ey = min(m["eye"], key=lambda p: (p[1], p[0]))
        put(ex, ey, "W", overwrite=True)

    outline(body | maw, m["skip"])
    for row in GRID:
        for i in range(W):
            if row[i] is None:
                row[i] = "."


def outline(cells, skip=frozenset()):
    for x, y in cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if (inb(nx, ny) and (nx, ny) not in cells and (nx, ny) not in skip
                    and GRID[ny][nx] is None):
                put(nx, ny, "X")


def shift(cells, dx, dy):
    return {(x + dx, y + dy) for x, y in cells if inb(x + dx, y + dy)}


def build(direction, phase):
    if direction == "down":
        m = front_masks(phase)
    elif direction == "left":
        m = side_masks(phase)
    elif direction == "right":
        m = {k: (flip(v) if isinstance(v, set) else v) for k, v in side_masks(phase).items()}
    else:
        m = back_masks(phase)
    m["phase"] = phase
    render(m)
    return [row[:] for row in GRID]


def frame_index(direction, phase):
    return DIRS.index(direction) * len(PHASES) + phase + 1  # 1-based


def ops_for(grid, frame):
    ops = []
    for y in range(H):
        x = 0
        while x < W:
            c = grid[y][x]
            if c == ".":
                x += 1
                continue
            run = 1
            while x + run < W and grid[y][x + run] == c:
                run += 1
            ops.append({"op": "draw_rect", "x": x, "y": y, "width": run, "height": 1,
                        "color": PALETTE[c], "filled": True, "frame": frame})
            x += run
    return ops


def all_ops():
    ops = []
    for d in DIRS:
        for p in range(len(PHASES)):
            ops += ops_for(build(d, p), frame_index(d, p))
    return ops


def show():
    for d in DIRS:
        for p in range(len(PHASES)):
            print(f"\n=== {d} / {PHASES[p]} (frame {frame_index(d, p)}) ===")
            for row in build(d, p):
                print("".join(row))


if __name__ == "__main__":
    if "--emit" in sys.argv:
        Path(__file__).with_name("monster_ops.json").write_text(
            json.dumps(all_ops(), ensure_ascii=False), encoding="utf-8")
        print("ops:", len(all_ops()))
    else:
        show()
