"""Dark reaper walk cycle: 32x32, 4 directions x 6 frames.

The reaper has no legs; the walk is read from a travelling ripple along the robe
hem plus the overall rise and fall and the alternating bone feet: the hem bottom
of each column is y = base + round(1.6 * sin(column phase + time phase)), and the
time phase advances per frame, so the ripple flows sideways along the robe; the
two bone feet lift and fall in antiphase with swing.

  python reaper.py            # print the ASCII frames
  python reaper.py --sheet    # local contact sheet .build/reaper_sheet.png
"""

import math
import sys
from pathlib import Path

W = H = 32
DIRS = ["down", "left", "right", "up"]
FRAMES = 6

P = {
    "L": "#3A4052",  # robe lit side
    "M": "#262B38",  # robe body
    "D": "#171B24",  # robe shadow
    "X": "#0A0C10",  # outline / hood cavity
    "R": "#FF3B30",  # eye
    "C": "#FFD5CF",  # eye glint
    "o": "#E8E4D8",  # bone
    "O": "#A79E8B",  # bone shadow
    "b": "#6B4A2B",  # scythe shaft
    "n": "#45301B",  # scythe shaft shadow
    "B": "#C9D3DE",  # scythe blade
    "W": "#EEF4FA",  # blade edge highlight
    "E": "#7C8894",  # blade spine
    "s": "#8E2F52",  # belt / rag
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


# ---------------------------------------------------------------- parts

def robe(d, ph):
    """Robe body: widens row by row, with sideways sway growing with depth; the hem
    uses a long-wavelength, low-amplitude travelling wave, so it reads as fabric
    undulating rather than dissolving."""
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
    rect(15 + lean, y - 1, 3, 3, "M")            # hood peak
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
        # Shadow on the hood's rear edge in side view: it must be drawn before the
        # eyes. Facing right it shares columns with the eye (x=21-22), and the
        # opposite order paints over both red eyes (inspect's palette then has no
        # #FF3B30).
        rect(9 if d == "left" else 21, y + 3, 2, 6, "D")
        rect(fx + (0 if d == "left" else 3), y + 7, 2, 2, "R")


def sleeves(d, ph):
    """The sleeves hang at the robe's sides and the bone hand grips the scythe
    shaft -- the hand must touch the shaft, otherwise it looks like a white speck
    floating on the body."""
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
    """The whole scythe translates with the gripping hand; moving only the ends
    would make the shaft stretch.

    The shaft is kept short on purpose: the bob is ±2px, and once the shaft bottom
    passes row 28 the outline hits the canvas's last row and the bbox bottom jumps
    from 30 to 32 -- that is the scythe poking the floor, not a step. Shortening
    moves only the shaft bottom; the blade and the gripping hand stay put.
    """
    y = ph["bob"]
    s = int(round(ph["swing"] * 2))
    if d == "down":
        # Front/back view: the blade sweeps outward from the body; inward it would
        # cross the face and cover the hood.
        x, top, shaft = 24, 3 + y - s, 23
        rect(x, top, 2, shaft, "b")
        rect(x, top, 1, shaft, "n")
        blade(x + 2, top, 1, 5)
    elif d == "up":
        x, top, shaft = 6, 3 + y - s, 23
        rect(x, top, 2, shaft, "n")
        rect(x + 1, top, 1, shaft, "b")
        blade(x - 1, top, -1, 5)
    else:
        x, top, shaft = (7 if d == "left" else 23), 2 + y - s, 24
        rect(x, top, 2, shaft, "b" if d == "left" else "n")
        rect(x, top, 1, shaft, "n")
        blade(x - 1 if d == "left" else x + 2, top, -1 if d == "left" else 1)


def blade(cx, cy, direction, span=11):
    """Lay the blade out column by column: a parabolic droop plus thinning from the
    shaft towards the tip. Spine on top (E), edge on the bottom (W)."""
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


def grid_lua(grid, title):
    """The Lua data file paint_grid consumes (in this build json.decode returns
    userdata, so dofile is the only way in).

    Rows are strings, None is written as '.' (transparent, skipped), and every
    colour is alpha=255.
    """
    used = {c for row in grid for c in row if c}
    palette = ", ".join(f'{c} = "{P[c]}"' for c in sorted(used))
    rows = ",\n  ".join('"%s"' % "".join(c or "." for c in row) for row in grid)
    return (f"-- {title}\nreturn {{\n  palette = {{ {palette} }},\n"
            f"  rows = {{\n  {rows},\n  }},\n}}\n")


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
