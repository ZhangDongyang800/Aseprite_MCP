"""16x16 health-potion icon design model.

Semantic masks -> outline -> shading, then serialise to a paint_grid Lua file.
The point is that the shape is authored once and the outline/shading are derived
consistently, not painted pixel by pixel by hand.
"""

from pathlib import Path

W = H = 16

PALETTE = {
    "K": "#241A2E",  # outline: hue-shifted plum, not pure black
    "C": "#5A3524",  # cork shadow
    "c": "#A9683C",  # cork mid
    "n": "#D79A5B",  # cork light
    "G": "#4B3B57",  # glass shadow
    "g": "#8A7895",  # glass mid
    "h": "#CFC2D2",  # glass highlight
    "R": "#6E2233",  # liquid shadow
    "r": "#B93A4A",  # liquid mid
    "o": "#ED6A5A",  # liquid light
    "W": "#FFF1DA",  # specular / bubble glint
}

BODY_CX, BODY_CY, BODY_RX, BODY_RY = 7.5, 10.2, 5.3, 4.0


def _ellipse(cx, cy, rx, ry, y_max=H - 1):
    out = set()
    for y in range(H):
        for x in range(W):
            if y > y_max:
                continue
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                out.add((x, y))
    return out


def build():
    body = _ellipse(BODY_CX, BODY_CY, BODY_RX, BODY_RY, y_max=14)
    neck = {(x, y) for x in range(6, 10) for y in range(4, 7)}
    cork = {(x, y) for x in range(6, 10) for y in range(2, 4)}
    lip = {(x, y) for x in range(5, 11) for y in (2,)}
    silhouette = body | neck | cork | lip

    # 1px outline outside the silhouette (4-neighbour dilation keeps it thin)
    outline = set()
    for x, y in silhouette:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (x + dx, y + dy)
            if 0 <= p[0] < W and 0 <= p[1] < H and p not in silhouette:
                outline.add(p)

    g = [["." for _ in range(W)] for _ in range(H)]
    for x, y in outline:
        g[y][x] = "K"

    for x, y in silhouette:
        if (x, y) in lip or (x, y) in cork:
            # cork grain: light on the upper-left, dark on the lower-right
            g[y][x] = "n" if (x <= 7 and y <= 3) else ("c" if y <= 3 or x <= 7 else "C")
        elif (x, y) in neck:
            g[y][x] = "h" if x == 6 else ("g" if x <= 8 else "G")
        else:
            # A shallow curve reads as a liquid surface; a straight line reads as a belt.
            surface = 8 if 4 <= x <= 11 else 9
            if y > surface:
                g[y][x] = "o" if (x + y <= 14) else ("r" if (x + y <= 20) else "R")
            elif y == surface:
                g[y][x] = "R"
            else:
                g[y][x] = "h" if (x <= 5 and y <= 7) else ("g" if x <= 7 else "G")

    # a small meniscus highlight on the left of the surface
    for x, y in ((4, 9), (5, 9)):
        if (x, y) in body:
            g[y][x] = "o"
    for x, y in ((4, 9), (5, 9)):
        if (x, y) in body:
            g[y][x] = "o"
    # upper-left glass specular, 2px vertical
    for x, y in ((4, 6), (4, 7)):
        if (x, y) in body:
            g[y][x] = "W"
    # two bubbles, separated from the rim so they never read as noise
    for x, y in ((9, 11), (10, 12)):
        if (x, y) in body:
            g[y][x] = "W"
    # cork/glass seam
    for x in range(6, 10):
        if (x, 4) in neck:
            g[4][x] = "C"

    # a 1px shadow notch under the cork on the neck (reads as the bottle shoulder)
    return g


def to_lua(g):
    used = sorted({ch for row in g for ch in row if ch != "."})
    pal = ", ".join(f'["{ch}"] = "{PALETTE[ch]}"' for ch in used)
    rows = ",\n".join('    "' + "".join(row) + '"' for row in g)
    return f"return {{\n  palette = {{ {pal} }},\n  rows = {{\n{rows},\n  }},\n}}\n"


def ascii_art(g):
    return "\n".join("".join(row) for row in g)


def preview(g, scale=16):
    from PIL import Image

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(g):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            h = PALETTE[ch].lstrip("#")
            px[x, y] = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    # checkerboard so transparency is visible
    bg = Image.new("RGBA", (W * scale, H * scale), (24, 24, 30, 255))
    bp = bg.load()
    for y in range(H * scale):
        for x in range(W * scale):
            if ((x // 4) + (y // 4)) % 2 == 0:
                bp[x, y] = (38, 38, 46, 255)
    bg.alpha_composite(img.resize((W * scale, H * scale), Image.Resampling.NEAREST))
    return bg


if __name__ == "__main__":
    g = build()
    out = Path(__file__).parent
    (out / "potion.lua").write_text(to_lua(g), encoding="utf-8")
    (out / ".build").mkdir(exist_ok=True)
    preview(g).save(out / ".build" / "potion_preview.png")
    print(ascii_art(g))
    print("colors:", len({c for row in g for c in row if c != "."}))
