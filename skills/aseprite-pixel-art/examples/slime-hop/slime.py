"""32x32 moss-slime hop cycle, 8 frames.

The body is a squash/stretch blob around a fixed ground anchor; the face and leaf
sprout are placed relative to the deformed body, so identity survives the motion.
Outputs one paint_grid Lua file per frame plus an offline preview.
"""

from pathlib import Path

W = H = 32
CX = 16.0

PALETTE = {
    "K": "#1E1A2E",  # outline
    "D": "#24523B",  # deep body
    "S": "#2F7A52",  # body shadow
    "M": "#4FAE68",  # body mid
    "L": "#8BD97A",  # body light
    "H": "#D6F5A0",  # body highlight
    "E": "#15121F",  # eye / mouth
    "W": "#FFF6D6",  # glint
    "O": "#6E2233",  # mouth interior
    "F": "#2F6B3A",  # leaf dark
    "f": "#7FBF4D",  # leaf mid
}

POSES = [
    # name, width scale, height scale, bottom y, face, leaf tilt, duration (s)
    ("neutral", 1.00, 0.92, 29, "normal", 0, 0.14),
    ("anticipate", 1.16, 0.72, 29, "squint", -1, 0.10),
    ("launch", 0.88, 1.20, 27, "wide", 1, 0.08),
    ("rise", 0.92, 1.12, 24, "wide", 1, 0.08),
    ("apex", 1.00, 0.94, 21, "wide", 0, 0.11),
    ("fall", 0.90, 1.12, 24, "normal", -1, 0.09),
    ("land", 1.22, 0.66, 29, "squint", -1, 0.07),
    ("recover", 1.05, 0.84, 29, "normal", 0, 0.13),
]


def _ellipse_mask(cx, cy, rx, ry, yb):
    out = set()
    for y in range(H):
        if y > yb:
            continue
        for x in range(W):
            dx = (x + 0.5 - cx) / rx
            dy = (y + 0.5 - cy) / ry
            if dx * dx + dy * dy <= 1.0:
                out.add((x, y))
    return out


def _leaf_pixels(top, tilt):
    # One broad leaf on a short stem. A single clear silhouette survives 1x
    # better than two one-pixel leaf lobes, and its tilt can lag the body.
    stem = [(16, top - 1), (16, top - 2), (16, top - 3)]
    leaves = []
    for lx, ly, ch in ((1, 3, "F"), (-1, 3, "F"),
                       (2, 4, "f"), (1, 4, "f"), (0, 4, "F"), (-1, 4, "f"), (-2, 4, "f"),
                       (1, 5, "f"), (0, 5, "H"), (-1, 5, "f"),
                       (0, 6, "H")):
        leaves.append((16 + lx + tilt, top - ly, ch))
    return stem, leaves


def build_pose(sx, sy, yb, face, tilt):
    h = max(8, round(15 * sy))
    rx = 10.0 * sx
    top = yb - h + 1
    cy = (top + yb) / 2.0
    ry = (yb - top + 1) / 2.0
    body = _ellipse_mask(CX, cy, rx, ry, yb)
    stem, leaf = _leaf_pixels(top, tilt)
    silhouette = body | set((x, y) for x, y, _ in leaf) | set(stem)

    outline = set()
    for x, y in silhouette:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (x + dx, y + dy)
            if 0 <= p[0] < W and 0 <= p[1] < H and p not in silhouette:
                outline.add(p)

    g = [["." for _ in range(W)] for _ in range(H)]
    for x, y in outline:
        g[y][x] = "K"

    # body value groups: upper-left light, lower-right shadow, dark rim
    for x, y in body:
        dx = (x + 0.5 - CX) / rx
        dy = (y + 0.5 - cy) / ry
        light = -(0.72 * dx + 0.58 * dy)
        r = (dx * dx + dy * dy) ** 0.5
        if light > 0.46:
            ch = "L"
        elif light > -0.02:
            ch = "M"
        elif light > -0.55:
            ch = "S"
        else:
            ch = "D"
        if r > 0.80 and (dx + dy) > 0.25:
            ch = "S" if ch != "D" else "D"
        if dy > 0.76:
            ch = "D"
        g[y][x] = ch

    # one clustered specular, plus a soft L ring around it
    hx, hy = CX - rx * 0.48, top + h * 0.28
    for x, y in body:
        q = ((x + 0.5 - hx) / 2.6) ** 2 + ((y + 0.5 - hy) / 1.7) ** 2
        if q <= 1.0:
            g[y][x] = "H"
        elif q <= 2.2 and g[y][x] in "MS":
            g[y][x] = "L"

    # despeckle the body only: a colour that appears once is almost always an accident
    for _ in range(2):
        for x, y in body:
            if g[y][x] in "KEW":
                continue
            nbrs = [g[y + dy][x + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= x + dx < W and 0 <= y + dy < H and (x + dx, y + dy) in body]
            if nbrs and g[y][x] not in nbrs:
                counts = {}
                for c in nbrs:
                    counts[c] = counts.get(c, 0) + 1
                g[y][x] = max(counts, key=counts.get)

    # leaf and stem
    for x, y in stem:
        if 0 <= y < H:
            g[y][x] = "F"
    for x, y, ch in leaf:
        if 0 <= x < W and 0 <= y < H:
            g[y][x] = ch

    # face: relative to the deformed body, so it never drifts between frames
    eye_w = 3
    eye_h = 2 if face == "squint" else 4
    eye_y = max(top + 2, min(top + int(round(h * 0.30)), yb - eye_h - 4))
    for ex in (int(CX) - 6, int(CX) + 3):
        for yy in range(eye_y, eye_y + eye_h):
            for xx in range(ex, ex + eye_w):
                if (xx, yy) in body:
                    g[yy][xx] = "E"
        if (ex, eye_y) in body:
            g[eye_y][ex] = "W"

    my = min(eye_y + eye_h + 3, yb - 3)
    if face == "wide":
        # dark open cavity with a red tongue; a red oval reads as a nose
        my = min(eye_y + eye_h + 2, yb - 4)
        rim = {(2, 0), (3, 0), (4, 0),
               (1, 1), (2, 1), (3, 1), (4, 1), (5, 1),
               (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2),
               (1, 3), (2, 3), (3, 3), (4, 3), (5, 3)}
        for mx, yy in rim:
            x, y = int(CX) - 3 + mx, my + yy
            if (x, y) in body:
                g[y][x] = "O" if yy == 3 and 2 <= mx <= 4 else "E"
        # one fang makes the dark cavity unambiguously a mouth
        tx = int(CX) - 3 + 3
        if (tx, my) in body:
            g[my][tx] = "W"
    elif face == "squint":
        for x in range(int(CX) - 2, int(CX) + 2):
            if (x, my) in body:
                g[my][x] = "E"
    else:
        for x, y in ((int(CX) - 2, my), (int(CX) + 1, my),
                     (int(CX) - 1, my + 1), (int(CX), my + 1)):
            if (x, y) in body:
                g[y][x] = "E"

    return g


def to_lua(g):
    used = sorted({ch for row in g for ch in row if ch != "."})
    pal = ", ".join(f'["{ch}"] = "{PALETTE[ch]}"' for ch in used)
    rows = ",\n".join('    "' + "".join(row) + '"' for row in g)
    return f"return {{\n  palette = {{ {pal} }},\n  rows = {{\n{rows},\n  }},\n}}\n"


def ascii_art(g):
    return "\n".join("".join(row) for row in g)


def rgba(ch):
    h = PALETTE[ch].lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def frames():
    out = []
    for name, sx, sy, yb, face, tilt, dur in POSES:
        g = build_pose(sx, sy, yb, face, tilt)
        out.append((name, g, dur))
    return out


def preview(outdir: Path, scale=8):
    from PIL import Image, ImageDraw

    fs = frames()
    cell_w = W * scale
    pad = 8
    sheet = Image.new("RGBA", (len(fs) * (cell_w + pad) + pad, cell_w + 32), (26, 26, 32, 255))
    d = ImageDraw.Draw(sheet)
    for i, (name, g, _) in enumerate(fs):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        px = img.load()
        for y, row in enumerate(g):
            for x, ch in enumerate(row):
                if ch != ".":
                    px[x, y] = rgba(ch)
        x0 = pad + i * (cell_w + pad)
        sheet.alpha_composite(img.resize((cell_w, cell_w), Image.Resampling.NEAREST), (x0, pad))
        d.text((x0, cell_w + 12), name, fill=(220, 220, 220, 255))
    sheet.save(outdir / "slime_contact.png")

    # true-size and 4x GIFs for motion review
    for s, name in ((1, "slime_1x.gif"), (4, "slime_4x.gif")):
        imgs = []
        for _, g, _ in fs:
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            px = img.load()
            for y, row in enumerate(g):
                for x, ch in enumerate(row):
                    if ch != ".":
                        px[x, y] = rgba(ch)
            imgs.append(img.resize((W * s, H * s), Image.Resampling.NEAREST))
        imgs[0].save(outdir / name, save_all=True, append_images=imgs[1:],
                     duration=[int(d * 1000) for _, _, d in fs], loop=0, disposal=2)


if __name__ == "__main__":
    here = Path(__file__).parent
    fr = frames()
    (here / "frames").mkdir(exist_ok=True)
    for i, (name, g, dur) in enumerate(fr, 1):
        (here / "frames" / f"frame_{i:02d}_{name}.lua").write_text(to_lua(g), encoding="utf-8")
    (here / ".build").mkdir(exist_ok=True)
    preview(here / ".build")
    print(ascii_art(fr[0][1]))
    print("frames:", [n for n, _, _ in fr])
