"""Q 版骑士行走循环：32x32，4 方向 x 6 帧。

行走靠一组相位通道驱动：swing（腿部前后/上下摆动，反相双腿）、bob（接触拍身体
下沉 1px）、sway（披风与盔缨甩动）。腿部摆幅刻意放大，因为素材最终按 4x 显示，
1px 的动作在这个尺寸下读不出来。

  python knight.py            # 打印 ASCII
  python knight.py --sheet    # 本地接触表 .build/knight_sheet.png
"""

import math
import sys
from pathlib import Path

W = H = 32
DIRS = ["down", "left", "right", "up"]
FRAMES = 6

P = {
    "s": "#DCE3EC",  # 亮银
    "m": "#AAB6C4",  # 中银
    "d": "#78838F",  # 暗银
    "X": "#2B303B",  # 描边
    "r": "#D94A3D",  # 披风/盔缨 亮红
    "e": "#9E2F26",  # 披风暗部
    "b": "#7A5230",  # 皮带
    "n": "#4A3218",  # 靴子
    "g": "#E0A93B",  # 金饰
    "k": "#15181F",  # 观察缝
    "w": "#F4F8FC",  # 高光
}

G = []


def clear():
    G[:] = [[None] * W for _ in range(H)]


def px(x, y, c):
    x, y = int(round(x)), int(round(y))
    if 0 <= x < W and 0 <= y < H and c:
        G[y][x] = c


def rect(x, y, w, h, c):
    for j in range(int(h)):
        for i in range(int(w)):
            px(x + i, y + j, c)


def ell(cx, cy, rx, ry, c):
    for y in range(max(0, int(cy - ry) - 1), min(H, int(cy + ry) + 2)):
        for x in range(max(0, int(cx - rx) - 1), min(W, int(cx + rx) + 2)):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                px(x, y, c)


def outline(c="X"):
    filled = {(x, y) for y in range(H) for x in range(W) if G[y][x]}
    for x, y in filled:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            if (x + dx, y + dy) not in filled:
                px(x + dx, y + dy, c)


def shine():
    """左上受光：色块左上边缘提亮一档。"""
    for y in range(1, H):
        for x in range(1, W):
            c = G[y][x]
            if c == "m" and G[y - 1][x] in (None, "X") and G[y][x - 1] in (None, "X"):
                G[y][x] = "s"
            elif c == "e" and G[y - 1][x] in (None, "X"):
                G[y][x] = "r"


def phase(i):
    s = math.sin(2 * math.pi * i / FRAMES)
    # 布料半帧滞后（follow-through）。纯正弦按 6 点均匀采样是对称的，
    # 会有两对帧量化后完全相同、被 GIF 编码器合并；滞后的 drag 打破这个简并。
    drag = math.sin(2 * math.pi * (i - 0.5) / FRAMES)
    return dict(swing=s, bob=int(round(abs(s))), sway=int(round(s * 2)),
                drag=drag, drag_sway=int(round(drag * 2)))


# ---------------------------------------------------------------- 部件

def legs(d, ph):
    s = ph["swing"]
    for name, sign in (("a", 1), ("b", -1)):
        v = s * sign                      # -1..1，正=这条腿在前
        front = v > 0.2
        if d in ("down", "up"):
            x0 = (12 if name == "a" else 17) + int(round(v))
            y0 = 21 - (2 if front else 0)
            rect(x0, y0, 4, 5, "m" if front else "d")
            rect(x0, y0 + 5, 4, 2, "n" if front else "X")
        else:
            back = -1 if d == "left" else 1
            x0 = 13 + int(round(v * 4)) * back
            y0 = 21 - (1 if front else 0)
            rect(x0, y0, 5, 5, "m" if front else "d")
            rect(x0, y0 + 5, 5, 2, "n" if front else "X")


def cape(d, ph):
    sw = ph["drag_sway"]
    if d == "down":
        rect(8 + sw, 13, 2, 11, "e")
        rect(22 - sw, 13, 2, 11, "r")
    elif d == "up":
        rect(9, 12, 14, 12, "e")
        rect(9 + sw, 12, 14, 3, "r")
        rect(10 + sw, 23, 12, 1, "r")
    else:
        back = -1 if d == "left" else 1
        x0 = 17 if d == "left" else 9
        rect(x0 + sw * back, 13, 6, 12, "e")
        rect(x0 + sw * back, 13, 6, 2, "r")
        rect(x0 + sw * back + back, 24, 5, 1, "r")


def torso(d, ph):
    y = 13 + ph["bob"]
    if d in ("down", "up"):
        rect(10, y, 12, 9, "m")
        rect(10, y + 7, 12, 1, "g")
        if d == "down":
            rect(15, y + 1, 2, 6, "s")
        else:
            rect(11, y + 1, 10, 8, "d")
            rect(11, y + 7, 10, 1, "n")
    else:
        x0 = 10 if d == "left" else 11
        rect(x0, y, 11, 9, "m")
        rect(x0, y + 7, 11, 1, "g")
        chest = 10 if d == "left" else 18
        rect(chest, y + 1, 3, 5, "s")


def arms(d, ph):
    y = 14 + ph["bob"]
    s = int(round(ph["swing"] * 2))
    if d == "down":
        rect(9, y - s, 2, 6, "d")
        rect(21, y + s, 2, 6, "s")
        px(22, y + s + 5, "s")
    elif d == "up":
        rect(9, y + s, 2, 6, "d")
        rect(21, y - s, 2, 6, "s")
    else:
        x = 13 if d == "left" else 15
        rect(x, y - s, 3, 6, "s")
        px(x, y - s + 5, "w")


def head(d, ph):
    y = 3 + ph["bob"]
    if d in ("down", "up"):
        ell(16, y + 6, 7.4, 6.2, "m")
        rect(9, y + 5, 14, 5, "m")
        rect(10, y + 2, 12, 2, "s")
        if d == "down":
            rect(11, y + 7, 10, 2, "k")
            rect(15, y + 7, 2, 2, "m")
            rect(10, y + 10, 12, 1, "d")
        else:
            rect(11, y + 8, 10, 2, "d")
    else:
        ell(16, y + 6, 7.0, 6.2, "m")
        rect(10 if d == "left" else 12, y + 5, 9, 5, "m")
        rect(11 if d == "left" else 17, y + 2, 4, 2, "s")
        slit = 10 if d == "left" else 20
        rect(slit, y + 7, 4, 2, "k")
        rect(9 if d == "left" else 21, y + 4, 2, 3, "d")   # 后脑/面颊护板


def plume(d, ph):
    y = ph["bob"]
    sw = ph["drag_sway"]
    if d in ("down", "up"):
        rect(15 + sw, y + 1, 2, 2, "r")
        rect(14 + sw, y + 2, 4, 2, "r")
        rect(14 + sw, y + 3, 4, 1, "e")
    else:
        back = -1 if d == "left" else 1
        x = 15 + sw * back
        rect(x, y + 1, 3, 3, "r")
        rect(x + back, y + 3, 3, 2, "r")
        rect(x + 2 * back, y + 4, 2, 2, "e")


def sword(d, ph):
    """剑随持剑手整体平移，不能只动护手——否则剑会被拉长。"""
    y = ph["bob"]
    s = int(round(ph["swing"] * 2))
    if d == "down":
        x, top, guard = 23, 5 + y + s, 19 + y + s
        rect(x, top, 2, guard - top, "s")
        rect(x, top, 1, guard - top, "w")
        rect(x - 1, guard, 4, 1, "g")
        rect(x, guard + 1, 2, 3, "b")
    elif d == "up":
        x, top, guard = 7, 5 + y + s, 19 + y + s
        rect(x, top, 2, guard - top, "d")
        rect(x + 1, top, 1, guard - top, "m")
        rect(x - 1, guard, 4, 1, "n")
        rect(x, guard + 1, 2, 3, "n")
    else:
        x, top, guard = (8 if d == "left" else 22), 4 + y - s, 18 + y - s
        rect(x, top, 2, guard - top, "s")
        rect(x, top, 1, guard - top, "w")
        rect(x - 1 if d == "left" else x, guard, 4, 1, "g")
        rect(x, guard + 1, 2, 3, "b")


PARTS = [cape, legs, torso, arms, head, plume, sword]


def build(d, i):
    clear()
    ph = phase(i)
    for part in PARTS:
        part(d, ph)
    shine()
    outline()
    return [row[:] for row in G]


def frame_index(d, i):
    return DIRS.index(d) * FRAMES + i + 1


def ops_for(grid, frame):
    ops = []
    for y in range(H):
        x = 0
        while x < W:
            c = grid[y][x]
            if c is None:
                x += 1
                continue
            run = 1
            while x + run < W and grid[y][x + run] == c:
                run += 1
            ops.append({"op": "draw_rect", "x": x, "y": y, "width": run, "height": 1,
                        "color": P[c], "filled": True, "frame": frame})
            x += run
    return ops


def all_ops():
    return [o for d in DIRS for i in range(FRAMES)
            for o in ops_for(build(d, i), frame_index(d, i))]


def show():
    for d in DIRS:
        for i in range(FRAMES):
            print(f"\n=== {d} / frame {i + 1} ===")
            for row in build(d, i):
                print("".join(c or "." for c in row))


def sheet(scale=5, path=None):
    from PIL import Image
    out = Image.new("RGB", (W * scale * FRAMES, H * scale * len(DIRS)), (30, 32, 28))
    for n, d in enumerate(DIRS):
        for i in range(FRAMES):
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            p = img.load()
            for y, row in enumerate(build(d, i)):
                for x, c in enumerate(row):
                    if c:
                        h = P[c].lstrip("#")
                        p[x, y] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
            big = img.resize((W * scale, H * scale), Image.NEAREST)
            out.paste(big, (i * W * scale, n * H * scale))
    path = Path(path or Path(__file__).parent / ".build" / "knight_sheet.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)
    return path, out.size


if __name__ == "__main__":
    print(*sheet()) if "--sheet" in sys.argv else show()
