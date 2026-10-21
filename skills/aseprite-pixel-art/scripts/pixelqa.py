#!/usr/bin/env python3
"""Offline QA for pixel-art deliverables produced through Aseprite MCP.

The MCP `inspect` tool reports one frame at a time and leaves `frame_diffs`
empty. This script checks the files that actually ship: grid sources, exported
PNG frames, GIF timing, and sprite-sheet cells, including frame-to-frame and
loop diffs.

Examples
--------
    python scripts/pixelqa.py grid examples/slime-hop/frames/*.lua --min-margin 1
    python scripts/pixelqa.py frames examples/slime-hop/export/frame*.png --loop
    python scripts/pixelqa.py gif examples/slime-hop/export/slime_hop.gif
    python scripts/pixelqa.py sheet examples/slime-hop/export/slime_hop_sheet.png \
        --cell 32x32 --columns 4 --frames examples/slime-hop/export/frame*.png
    python scripts/pixelqa.py contact examples/slime-hop/export/frame*.png \
        --out /tmp/slime_contact.png --scale 8 --bg dark

Exit code is 1 when a hard check fails; warnings do not fail unless --strict.
Requires Pillow (already a dependency of the MCP server).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageSequence
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("pixelqa needs Pillow: pip install pillow") from exc

NEAR_DUPLICATE_DELTA = 8
MAX_EXACT_DIFF_PIXELS = 1_000_000


# --------------------------------------------------------------------------- helpers


def _alpha_values(img: Image.Image) -> set[int]:
    return set(img.getchannel("A").tobytes())


def _visible_colors(img: Image.Image) -> list[tuple[int, tuple[int, int, int, int]]]:
    hist = img.getcolors(maxcolors=1_000_000) or []
    return sorted(((n, c) for n, c in hist if c[3] > 0), key=lambda t: (-t[0], t[1]))


def _isolated(alpha: Image.Image) -> int:
    mask = alpha.point(lambda v: 255 if v > 0 else 0, mode="L")
    w, h = mask.size
    padded = Image.new("L", (w + 2, h + 2), 0)
    padded.paste(mask, (1, 1))
    nbr = Image.new("L", padded.size, 0)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nbr = ImageChops.lighter(nbr, ImageChops.offset(padded, dx, dy))
    nbr = nbr.crop((1, 1, w + 1, h + 1))
    alone = ImageChops.darker(mask, ImageChops.invert(nbr))
    return sum(alone.histogram()[1:])


def _near_dupes(colors: list[tuple[int, int, int, int]]) -> list[list[str]]:
    out = []
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            a, b = colors[i], colors[j]
            if all(abs(a[k] - b[k]) <= NEAR_DUPLICATE_DELTA for k in range(3)):
                out.append(["#%02X%02X%02X" % a[:3], "#%02X%02X%02X" % b[:3]])
    return out


def image_stats(img: Image.Image) -> dict:
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    visible = _visible_colors(img)
    colors = [c for _, c in visible]
    opaque = sum(n for n, _ in visible)
    w, h = img.size
    margins = None
    if bbox:
        margins = {"left": bbox[0], "top": bbox[1],
                   "right": w - bbox[2], "bottom": h - bbox[3]}
    return {
        "width": w,
        "height": h,
        "alpha_values": sorted(_alpha_values(img)),
        "semi_transparent_pixels": sum(n for n, c in (img.getcolors(1_000_000) or [])
                                       if 0 < c[3] < 255),
        "opaque_pixels": opaque,
        "coverage": round(opaque / (w * h), 4) if w and h else 0,
        "color_count": len(colors),
        "palette": ["#%02X%02X%02X" % c[:3] for c in colors],
        "near_duplicate_colors": _near_dupes(colors[:64]),
        "bbox": ({"x": bbox[0], "y": bbox[1], "width": bbox[2] - bbox[0],
                  "height": bbox[3] - bbox[1]} if bbox else None),
        "margins": margins,
        "isolated_pixels": _isolated(alpha),
    }


def changed_pixels(a: Image.Image, b: Image.Image) -> tuple[int | None, tuple | None]:
    a = a.convert("RGBA")
    b = b.convert("RGBA")
    if a.size != b.size:
        return None, None
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    if bbox is None:
        return 0, None
    if a.width * a.height <= MAX_EXACT_DIFF_PIXELS:
        raw = diff.tobytes()
        n = sum(1 for i in range(0, len(raw), 4) if raw[i:i + 4] != b"\0\0\0\0")
    else:
        n = None
    return n, bbox


def _hard(stats: dict, args) -> list[str]:
    fail = []
    if stats["semi_transparent_pixels"] and not args.allow_semi:
        fail.append(f"{stats['semi_transparent_pixels']} semi-transparent pixels")
    if stats["isolated_pixels"] > args.max_isolated:
        fail.append(f"{stats['isolated_pixels']} isolated pixels (max {args.max_isolated})")
    if args.max_colors and stats["color_count"] > args.max_colors:
        fail.append(f"{stats['color_count']} colors (max {args.max_colors})")
    if args.min_margin is not None and stats["margins"]:
        tight = {k: v for k, v in stats["margins"].items() if v < args.min_margin}
        if tight:
            fail.append(f"content touches the edge: margins {tight} (min {args.min_margin})")
    if stats["near_duplicate_colors"]:
        fail.append(f"near-duplicate colors: {stats['near_duplicate_colors']}")
    return fail


def _load_pngs(paths: list[str]) -> list[tuple[str, Image.Image]]:
    out = []
    for raw in paths:
        p = Path(raw)
        if any(ch in raw for ch in "*?[]"):
            matches = sorted(Path().glob(raw)) if not p.is_absolute() else sorted(p.parent.glob(p.name))
            for m in matches:
                out.append((str(m), Image.open(m)))
        else:
            out.append((str(p), Image.open(p)))
    if not out:
        raise SystemExit("no PNG files matched")
    return out


# --------------------------------------------------------------------------- grid


_ROW_RE = re.compile(r'^\s*"(.*)"\s*,?\s*$')
_PAL_RE = re.compile(r'\["(.+?)"\]\s*=\s*"(#[0-9A-Fa-f]{6})"')
_LUA_CHAR = re.compile(r"^.$", re.S)


def parse_grid(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    palette = {m.group(1): m.group(2) for m in _PAL_RE.finditer(text)}
    rows = []
    in_rows = False
    for line in text.splitlines():
        if "rows" in line and "{" in line:
            in_rows = True
            continue
        if not in_rows:
            continue
        if line.strip().startswith("}"):
            break
        m = _ROW_RE.match(line)
        if m:
            rows.append(m.group(1))
    if not rows:
        raise SystemExit(f"{path}: no rows found (expected Lua data returning {{palette=..., rows={{...}}}})")
    width = len(rows[0])
    problems = []
    if any(len(r) != width for r in rows):
        problems.append("rows have different widths")
    if not palette:
        problems.append("palette is empty")
    for key in palette:
        if not _LUA_CHAR.match(key):
            problems.append(f"palette key {key!r} is not one character")
    used = {ch for row in rows for ch in row if ch != "."}
    missing = sorted(used - set(palette))
    unused = sorted(set(palette) - used)
    if missing:
        problems.append(f"codes missing from palette: {missing}")
    if unused:
        problems.append(f"palette entries never used: {unused}")
    rgb = []
    for key in sorted(used & set(palette)):
        value = palette[key].lstrip("#")
        rgb.append(tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (255,))

    w, h = width, len(rows)
    solid = {(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch != "."}
    bbox = None
    if solid:
        xs = [p[0] for p in solid]
        ys = [p[1] for p in solid]
        bbox = {"x": min(xs), "y": min(ys),
                "width": max(xs) - min(xs) + 1, "height": max(ys) - min(ys) + 1}
    iso = 0
    for x, y in solid:
        if all((x + dx, y + dy) not in solid
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            iso += 1
    return {
        "file": str(path),
        "width": w,
        "height": h,
        "colors_used": len(used),
        "palette": sorted(palette.items()),
        "near_duplicate_colors": _near_dupes(rgb),
        "bbox": bbox,
        "coverage": round(len(solid) / (w * h), 4) if w and h else 0,
        "isolated_pixels": iso,
        "problems": problems,
        "_rows": rows,
    }


def _grid_diff(a: dict, b: dict):
    if (a["width"], a["height"]) != (b["width"], b["height"]):
        return None, None
    changed = 0
    xs, ys = [], []
    for y, (ra, rb) in enumerate(zip(a["_rows"], b["_rows"])):
        if ra == rb:
            continue
        for x, (ca, cb) in enumerate(zip(ra, rb)):
            if ca != cb:
                changed += 1
                xs.append(x)
                ys.append(y)
    if not changed:
        return 0, None
    return changed, {"x": min(xs), "y": min(ys),
                     "width": max(xs) - min(xs) + 1, "height": max(ys) - min(ys) + 1}


def cmd_grid(args) -> int:
    reports = [parse_grid(Path(p)) for p in args.files]
    fails = []
    for r in reports:
        if r["problems"]:
            fails.extend(f"{r['file']}: {p}" for p in r["problems"])
        if args.min_margin is not None and r["bbox"]:
            margins = {
                "left": r["bbox"]["x"], "top": r["bbox"]["y"],
                "right": r["width"] - r["bbox"]["x"] - r["bbox"]["width"],
                "bottom": r["height"] - r["bbox"]["y"] - r["bbox"]["height"],
            }
            tight = {k: v for k, v in margins.items() if v < args.min_margin}
            if tight:
                fails.append(f"{r['file']}: content touches the edge: {tight}")
        if args.expect and (r["width"], r["height"]) != tuple(args.expect):
            fails.append(f"{r['file']}: size {r['width']}x{r['height']} != {args.expect[0]}x{args.expect[1]}")
        if r["isolated_pixels"]:
            fails.append(f"{r['file']}: {r['isolated_pixels']} isolated pixels")
        if args.max_colors and r["colors_used"] > args.max_colors:
            fails.append(f"{r['file']}: {r['colors_used']} colors (max {args.max_colors})")
        if r["near_duplicate_colors"]:
            fails.append(f"{r['file']}: near-duplicate colors: {r['near_duplicate_colors']}")

    if len(reports) > 1:
        sizes = {(r["width"], r["height"]) for r in reports}
        if len(sizes) != 1:
            fails.append(f"frames disagree on size: {sorted(sizes)}")
        # A frame may legitimately use a subset of the palette; it may not
        # redefine a code to a different colour.
        seen: dict[str, str] = {}
        for r in reports:
            for key, hex_value in r["palette"]:
                if key in seen and seen[key] != hex_value:
                    fails.append(f"palette drift: {key!r} is {seen[key]} in one frame and {hex_value} in another")
                seen[key] = hex_value
        diffs = []
        for i in range(len(reports) - 1):
            n, bbox = _grid_diff(reports[i], reports[i + 1])
            diffs.append({"from": Path(reports[i]["file"]).name,
                          "to": Path(reports[i + 1]["file"]).name,
                          "changed_pixels": n, "bbox": bbox})
            if n == 0:
                fails.append(f"{reports[i]['file']} and {reports[i + 1]['file']} are identical")
        loop = None
        if args.loop:
            n, bbox = _grid_diff(reports[-1], reports[0])
            loop = {"changed_pixels": n, "bbox": bbox}
            if n == 0:
                fails.append("last and first grids are identical; no loop motion")
    else:
        diffs, loop = [], None

    public = [{k: v for k, v in r.items() if k != "_rows"} for r in reports]
    print(json.dumps({"ok": not fails, "reports": public, "diffs": diffs, "loop": loop,
                      "failures": fails}, indent=2))
    return 1 if fails else 0


# --------------------------------------------------------------------------- frames


def cmd_frames(args) -> int:
    loaded = _load_pngs(args.files)
    stats = []
    failures = []
    for name, im in loaded:
        s = image_stats(im)
        s["file"] = name
        failures.extend(f"{name}: {m}" for m in _hard(s, args))
        stats.append(s)

    diffs = []
    for i in range(len(loaded) - 1):
        n, bbox = changed_pixels(loaded[i][1], loaded[i + 1][1])
        diffs.append({"from": Path(loaded[i][0]).name, "to": Path(loaded[i + 1][0]).name,
                      "changed_pixels": n, "bbox": bbox})
        if n == 0:
            failures.append(f"{loaded[i][0]} and {loaded[i + 1][0]} are identical")
    loop = None
    if args.loop and len(loaded) > 1:
        n, bbox = changed_pixels(loaded[-1][1], loaded[0][1])
        loop = {"changed_pixels": n, "bbox": bbox}
        if n == 0:
            failures.append("last and first frames are identical; no loop motion")

    masses = [s["opaque_pixels"] for s in stats if s["opaque_pixels"]]
    ratios = {"mass_max_min": round(max(masses) / min(masses), 3)} if masses else {}
    if masses and max(masses) / min(masses) > args.max_mass_ratio:
        failures.append(f"opaque mass varies {max(masses) / min(masses):.2f}x (max {args.max_mass_ratio})")

    print(json.dumps({"ok": not failures, "frames": stats, "diffs": diffs,
                      "loop": loop, "ratios": ratios, "failures": failures}, indent=2))
    return 1 if failures else 0


# --------------------------------------------------------------------------- gif


def cmd_gif(args) -> int:
    gif = Image.open(args.file)
    frames = []
    for idx, fr in enumerate(ImageSequence.Iterator(gif), 1):
        im = fr.convert("RGBA")
        s = image_stats(im)
        s["file"] = f"{args.file}#{idx}"
        s["duration_ms"] = fr.info.get("duration")
        frames.append(s)
    durations = [f["duration_ms"] for f in frames]
    failures = []
    if args.expect_durations:
        want = [int(x.strip()) for x in args.expect_durations.split(",") if x.strip()]
        if durations != want:
            failures.append(f"durations {durations} != expected {want}")
    if args.expect_frames and len(frames) != args.expect_frames:
        failures.append(f"{len(frames)} frames != expected {args.expect_frames}")
    if len({(f["width"], f["height"]) for f in frames}) != 1:
        failures.append("GIF frames have different sizes")
    for f in frames:
        failures.extend(f"{f['file']}: {m}" for m in _hard(f, args) if "semi-transparent" not in m)
    print(json.dumps({"ok": not failures, "size": gif.size, "loop": gif.info.get("loop"),
                      "durations_ms": durations, "frames": frames, "failures": failures}, indent=2))
    return 1 if failures else 0


# --------------------------------------------------------------------------- sheet


def cmd_sheet(args) -> int:
    sheet = Image.open(args.file).convert("RGBA")
    cw, ch = args.cell
    cols = args.columns or max(1, sheet.width // cw)
    rows = (sheet.height + ch - 1) // ch
    cells = []
    fails = []
    expected = _load_pngs(args.frames) if args.frames else []
    for r in range(rows):
        for c in range(cols):
            box = (c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)
            cell = sheet.crop(box)
            s = image_stats(cell)
            s["cell"] = {"row": r, "column": c, "box": box}
            if s["opaque_pixels"] == 0:
                fails.append(f"sheet cell r{r}c{c} is empty")
            if s["margins"] and min(s["margins"].values()) == 0 and s["opaque_pixels"]:
                s["warning"] = "content touches the cell edge (bleed risk)"
            cells.append(s)
            idx = r * cols + c
            if expected and idx < len(expected):
                n, _ = changed_pixels(cell, expected[idx][1])
                s["matches_frame_file"] = n == 0
                if n != 0:
                    fails.append(f"sheet cell r{r}c{c} differs from {expected[idx][0]}")
    print(json.dumps({"ok": not fails, "size": sheet.size, "cell": [cw, ch],
                      "columns": cols, "rows": rows, "cells": cells,
                      "failures": fails}, indent=2))
    return 1 if fails else 0


# --------------------------------------------------------------------------- contact


def cmd_contact(args) -> int:
    loaded = _load_pngs(args.files)
    scale = args.scale
    w = max(im.width for _, im in loaded) * scale
    h = max(im.height for _, im in loaded) * scale
    cols = args.columns or min(len(loaded), 8)
    rows = (len(loaded) + cols - 1) // cols
    pad = 8
    label_h = 14 if args.labels else 0
    out = Image.new("RGBA", (cols * (w + pad) + pad, rows * (h + pad + label_h) + pad),
                    (28, 28, 34, 255))
    draw = ImageDraw.Draw(out)
    for i, (name, im) in enumerate(loaded):
        c, r = i % cols, i // cols
        x, y = pad + c * (w + pad), pad + r * (h + pad + label_h)
        if args.bg == "checker":
            bg = Image.new("RGBA", (w, h), (32, 32, 38, 255))
            for yy in range(h):
                for xx in range(w):
                    if ((xx // 8) + (yy // 8)) % 2:
                        bg.putpixel((xx, yy), (44, 44, 52, 255))
            out.alpha_composite(bg, (x, y))
        elif args.bg == "light":
            out.alpha_composite(Image.new("RGBA", (w, h), (232, 231, 226, 255)), (x, y))
        up = im.convert("RGBA").resize((im.width * scale, im.height * scale),
                                       Image.Resampling.NEAREST)
        out.alpha_composite(up, (x, y))
        if args.labels:
            draw.text((x, y + h + 1), f"{i + 1} {Path(name).stem}", fill=(230, 230, 230, 255))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out)
    print(json.dumps({"ok": True, "output": args.out, "size": out.size,
                      "panel": [w, h], "count": len(loaded)}, indent=2))
    return 0


# --------------------------------------------------------------------------- cli


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--max-colors", type=int, default=32)
    common.add_argument("--allow-semi", action="store_true")
    common.add_argument("--max-isolated", type=int, default=0)
    common.add_argument("--min-margin", type=int, default=None)
    common.add_argument("--strict", action="store_true")

    g = sub.add_parser("grid", parents=[common], help="validate paint_grid Lua sources")
    g.add_argument("files", nargs="+")
    g.add_argument("--expect", nargs=2, type=int, metavar=("W", "H"))
    g.add_argument("--loop", action="store_true")
    g.set_defaults(func=cmd_grid)

    f = sub.add_parser("frames", parents=[common], help="validate exported PNG frames")
    f.add_argument("files", nargs="+")
    f.add_argument("--loop", action="store_true")
    f.add_argument("--max-mass-ratio", type=float, default=1.6)
    f.set_defaults(func=cmd_frames)

    gi = sub.add_parser("gif", parents=[common], help="validate an exported GIF")
    gi.add_argument("file")
    gi.add_argument("--expect-durations", help="comma-separated milliseconds")
    gi.add_argument("--expect-frames", type=int)
    gi.set_defaults(func=cmd_gif)

    sh = sub.add_parser("sheet", parents=[common], help="validate sprite-sheet cells")
    sh.add_argument("file")
    sh.add_argument("--cell", required=True, type=lambda s: tuple(int(x) for x in s.lower().split("x")))
    sh.add_argument("--columns", type=int)
    sh.add_argument("--frames", nargs="+", help="frame PNGs to compare cell by cell")
    sh.set_defaults(func=cmd_sheet)

    ct = sub.add_parser("contact", help="build a labeled visual contact sheet")
    ct.add_argument("files", nargs="+")
    ct.add_argument("--out", required=True)
    ct.add_argument("--scale", type=int, default=8)
    ct.add_argument("--columns", type=int, default=4)
    ct.add_argument("--bg", choices=("dark", "light", "checker"), default="dark")
    ct.add_argument("--labels", action="store_true")
    ct.set_defaults(func=cmd_contact)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
