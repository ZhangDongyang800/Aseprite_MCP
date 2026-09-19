"""暗黑死神行走循环：32x32，4 方向 x 6 帧。

死神没有腿，靠袍摆的行波涟漪 + 整体起伏 + 骨脚交替读出"走"：
下摆每列的底边 y = 基准 + round(1.6 * sin(列相位 + 时间相位))，
时间相位按帧推进，于是波纹沿袍子横向流动；两条骨脚按 swing 反相抬落。

  python reaper.py            # 打印 ASCII
  python reaper.py --sheet    # 本地接触表 .build/reaper_sheet.png
"""

import math
import sys
from pathlib import Path

W = H = 32
DIRS = ["down", "left", "right", "up"]
FRAMES = 6

P = {
    "L": "#3A4052",  # 袍亮面
    "M": "#262B38",  # 袍主体
    "D": "#171B24",  # 袍暗部
    "X": "#0A0C10",  # 描边 / 兜帽内腔
    "R": "#FF3B30",  # 眼
    "C": "#FFD5CF",  # 眼神光
    "o": "#E8E4D8",  # 骨
    "O": "#A79E8B",  # 骨暗部
    "b": "#6B4A2B",  # 镰柄
    "n": "#45301B",  # 镰柄暗部
    "B": "#C9D3DE",  # 镰刃
    "W": "#EEF4FA",  # 刃口高光
    "E": "#7C8894",  # 刃背
    "s": "#8E2F52",  # 腰带/破布
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


def phase(i):
    s = math.sin(2 * math.pi * i / FRAMES)
    return dict(swing=s, bob=int(round(abs(s))), sway=int(round(s * 2)),
                wave=2 * math.pi * i / FRAMES)


# ---------------------------------------------------------------- 部件

def robe(d, ph):
    """袍身：逐行加宽 + 随深度增大的横向摆动；底边用宽波长小振幅的行波，
    读作布料起伏而不是溶解。"""
    top = 12 + ph["bob"]
    lean = {"down": 0, "up": 0, "left": -1, "right": 1}[d]
    spans = {}
    for k in range(14):
        y = top + k
        if y >= H - 4:
            break
        f = k / 13
        half = 5.0 + f * 5.2
        cx = 16 + lean + ph["sway"] * f * 1.2
        for x in range(int(round(cx - half)), int(round(cx + half)) + 1):
            lo, hi = spans.get(x, (y, y))
            spans[x] = (min(lo, y), max(hi, y))
    cols = {x: hi + int(round(1.0 * math.sin(x * 0.5 + ph["wave"])))
            for x, (_, hi) in spans.items()}
    left, right = min(cols), max(cols)
    for x, bot in cols.items():
        for y in range(spans[x][0], bot + 1):
            if x <= left + 1:
                c = "L"
            elif x >= right - 1 or y >= bot - 1:
                c = "D"
            else:
                c = "M"
            if d == "left" and x > (left + right) / 2 + 2:
                c = "D"
            if d == "right" and x < (left + right) / 2 - 2:
                c = "D"
            px(x, y, c)
    rect(12 + lean, 15 + ph["bob"], 8, 1, "s")


def feet(d, ph):
    s = ph["swing"]
    for name, sign in (("a", 1), ("b", -1)):
        v = s * sign
        lift = 2 if v > 0.2 else 0
        if d in ("down", "up"):
            x0 = (13 if name == "a" else 17) + int(round(v))
        else:
            back = -1 if d == "left" else 1
            x0 = 15 + int(round(v * 3)) * back
        y0 = 27 - lift
        rect(x0, y0, 2, 2, "o" if v > 0.2 else "O")


def hood(d, ph):
    y = 4 + ph["bob"]
    lean = {"down": 0, "up": 0, "left": -1, "right": 1}[d]
    ell(16 + lean, y + 6, 7.2, 6.6, "M")
    rect(9 + lean, y + 5, 15, 5, "M")
    rect(15 + lean, y - 1, 3, 3, "M")            # 兜帽尖顶
    rect(16 + lean, y - 2, 2, 2, "L")
    rect(10 + lean, y + 2, 4, 2, "L")
    if d == "down":
        ell(16, y + 7, 4.6, 4.0, "X")
        for ex in (14, 18):
            rect(ex, y + 7, 2, 2, "R")
            px(ex, y + 7, "C")
    elif d == "up":
        ell(16, y + 7, 4.0, 3.4, "D")
        rect(13, y + 6, 6, 1, "X")
    else:
        fx = 11 if d == "left" else 18
        ell(fx + 1.5, y + 7, 3.4, 3.8, "X")
        rect(fx + (0 if d == "left" else 3), y + 7, 2, 2, "R")
        rect(9 if d == "left" else 21, y + 3, 2, 6, "D")


def sleeves(d, ph):
    """袖口垂在袍侧，骨手握住镰柄——手必须贴住柄，不然像飘在身上的白点。"""
    y = 13 + ph["bob"]
    s = int(round(ph["swing"] * 2))
    if d == "down":
        rect(9, y + s, 3, 7, "D")
        rect(20, y - s, 3, 6, "M")
        rect(22, y - s + 4, 3, 3, "o")
    elif d == "up":
        rect(9, y - s, 3, 6, "D")
        rect(20, y + s, 3, 7, "D")
        rect(6, y - s + 4, 3, 3, "o")
    else:
        x, hx = (19, 6) if d == "left" else (10, 23)
        rect(x, y - s, 3, 6, "M")
        rect(hx, y - s + 4, 3, 3, "o")


def scythe(d, ph):
    """镰刀整体随持握手平移，只动端点会让柄伸缩。"""
    y = ph["bob"]
    s = int(round(ph["swing"] * 2))
    if d == "down":
        # 正/背视：刃朝身体外侧扫出，向内会横过脸把兜帽盖掉
        x, top = 24, 3 + y - s
        rect(x, top, 2, 25, "b")
        rect(x, top, 1, 25, "n")
        blade(x + 2, top, 1, 5)
    elif d == "up":
        x, top = 6, 3 + y - s
        rect(x, top, 2, 25, "n")
        rect(x + 1, top, 1, 25, "b")
        blade(x - 1, top, -1, 5)
    else:
        x, top = (7 if d == "left" else 23), 2 + y - s
        rect(x, top, 2, 26, "b" if d == "left" else "n")
        rect(x, top, 1, 26, "n")
        blade(x - 1 if d == "left" else x + 2, top, -1 if d == "left" else 1)


def blade(cx, cy, direction, span=11):
    """逐列铺刃：抛物线下坠 + 由柄向刃尖收薄。脊在上（E）、刃口在下（W）。"""
    for i in range(span + 1):
        x = cx + direction * i
        u = i / span
        y = cy + 6.5 * u * u
        th = max(1, round(4.0 * (1 - u)) + 1)
        for t in range(th):
            c = "E" if t == 0 else ("W" if t == th - 1 else "B")
            px(x, y + t, c)


PARTS = [scythe, feet, robe, sleeves, hood]


def build(d, i):
    clear()
    ph = phase(i)
    for part in PARTS:
        part(d, ph)
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


def sheet(scale=4, path=None):
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
            out.paste(img.resize((W * scale, H * scale), Image.NEAREST),
                      (i * W * scale, n * H * scale))
    path = Path(path or Path(__file__).parent / ".build" / "reaper_sheet.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)
    return path, out.size


if __name__ == "__main__":
    print(*sheet()) if "--sheet" in sys.argv else show()
