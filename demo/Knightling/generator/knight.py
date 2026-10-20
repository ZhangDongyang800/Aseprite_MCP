"""Chibi knight walk cycle: 32x32, 4 directions x 6 frames.

The walk is driven by a set of phase channels: swing (the legs swinging fore/aft
and up/down, the two legs in antiphase), bob (the body sinking 1px on the contact
beat), sway (the cape and plume whipping). The leg amplitude is deliberately
exaggerated, because the asset is finally shown at 4x and 1px of motion is
unreadable at that size.

  python knight.py            # print the ASCII frames
  python knight.py --sheet    # local contact sheet .build/knight_sheet.png
"""

import math
import sys
from pathlib import Path

W = H = 32
DIRS = ["down", "left", "right", "up"]
FRAMES = 6

P = {
    "s": "#DCE3EC",  # bright silver
    "m": "#AAB6C4",  # mid silver
    "d": "#78838F",  # dark silver
    "X": "#2B303B",  # outline
    "r": "#D94A3D",  # cape / plume, bright red
    "e": "#9E2F26",  # cape shadow
    "b": "#7A5230",  # belt
    "n": "#4A3218",  # boots
    "g": "#E0A93B",  # gold trim
    "k": "#15181F",  # vision slit
    "w": "#F4F8FC",  # highlight
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
    """Light from the upper left: lift the block's upper-left edge one step."""
    for y in range(1, H):
        for x in range(1, W):
            c = G[y][x]
            if c == "m" and G[y - 1][x] in (None, "X") and G[y][x - 1] in (None, "X"):
                G[y][x] = "s"
            elif c == "e" and G[y - 1][x] in (None, "X"):
                G[y][x] = "r"


def phase(i):
    s = math.sin(2 * math.pi * i / FRAMES)
    # Cloth lags half a frame (follow-through). A pure sine sampled evenly at 6
    # points is symmetric, so two pairs of frames quantize to the same pose and
    # the GIF encoder merges them; the lagging drag breaks that degeneracy.
    drag = math.sin(2 * math.pi * (i - 0.5) / FRAMES)
    return dict(swing=s, bob=int(round(abs(s))), sway=int(round(s * 2)),
                drag=drag, drag_sway=int(round(drag * 2)))


# ---------------------------------------------------------------- parts

def legs(d, ph):
    s = ph["swing"]
    for name, sign in (("a", 1), ("b", -1)):
        v = s * sign                      # -1..1, positive = this leg is forward
        front = v > 0.2
        if d in ("down", "up"):
            # Front/back leg groups must be symmetric about canvas centre 15.5:
            # 11..14 and 16..19.
            x0 = (11 if name == "a" else 16) + int(round(v))
            y0 = 21 - (2 if front else 0)
            rect(x0, y0, 4, 5, "m" if front else "d")
            rect(x0, y0 + 5, 4, 2, "n" if front else "X")
        else:
            back = -1 if d == "left" else 1
            # Same for side views: the swing axis differs by 1 between the two
            # directions (13 / 14), otherwise the right-facing legs all shift 1px left.
            x0 = (13 if d == "left" else 14) + int(round(v * 4)) * back
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
        # The chest highlight sits on the front of the body: 10..12 facing left,
        # mirrored to 19..21 facing right.
        chest = 10 if d == "left" else 19
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
        x = 13 if d == "left" else 16
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
        rect(10 if d == "left" else 13, y + 5, 9, 5, "m")
        rect(11 if d == "left" else 17, y + 2, 4, 2, "s")
        # The vision slit must stay inside the helmet's face: 18..21 facing right
        # (mirrored from 10..13 facing left). The old 20..23 had half the slit
        # covered by the blade (x=22,23).
        slit = 10 if d == "left" else 18
        rect(slit, y + 7, 4, 2, "k")
        rect(9 if d == "left" else 21, y + 4, 2, 3, "d")   # back of head / cheek guard


def plume(d, ph):
    y = ph["bob"]
    sw = ph["drag_sway"]
    if d in ("down", "up"):
        rect(15 + sw, y + 1, 2, 2, "r")
        rect(14 + sw, y + 2, 4, 2, "r")
        rect(14 + sw, y + 3, 4, 1, "e")
    else:
        back = -1 if d == "left" else 1
        x = (15 if d == "left" else 14) + sw * back
        rect(x, y + 1, 3, 3, "r")
        rect(x + back, y + 3, 3, 2, "r")
        rect(x + 2 * back, y + 4, 2, 2, "e")


def sword(d, ph):
    """The sword translates as a whole with the sword hand; moving only the guard
    would stretch the blade."""
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
        # The guard extends 1px each side of the blade axis (facing right it once
        # extended only to the right, which made the whole sword look off-centre).
        rect(x - 1, guard, 4, 1, "g")
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


def grid_rows(d, i):
    """build()'s character grid -> paint_grid string rows ('.' = transparent, skipped)."""
    return ["".join(c or "." for c in row) for row in build(d, i)]


def grid_lua(d, i):
    """The Lua data file that paint_grid consumes.

    Not JSON: in this build json.decode returns userdata, so pairs()/# do not work
    and the grid can only reach the op as a Lua table file loaded with dofile. The
    palette only carries the keys this frame actually uses.
    """
    rows = grid_rows(d, i)
    used = sorted({key for row in rows for key in row if key != "."})
    palette = ", ".join(f'["{key}"] = "{P[key]}"' for key in used)
    body = ",\n  ".join(f'"{row}"' for row in rows)
    return (f"-- chibi knight: {d} frame {i + 1} of {FRAMES}\n"
            f"return {{\n  palette = {{ {palette} }},\n  rows = {{\n  {body},\n  }},\n}}\n")


def opaque_count(d, i):
    """Opaque pixel count of this frame: inspect's coverage is checked against it."""
    return sum(1 for row in build(d, i) for c in row if c)


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
