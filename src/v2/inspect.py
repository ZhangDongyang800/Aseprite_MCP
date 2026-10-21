"""Perception metrics computed from the exported PNG + Lua metadata (spec §8).

Every metric goes through PIL's C implementation: a per-pixel Python loop would drag a
single inspect of a 2048² canvas from milliseconds to ten-plus seconds, and "draw, then
take a look" is the most frequent call this tool gets.
"""

from pathlib import Path

from PIL import Image, ImageChops

# Pairwise near-duplicate comparison is O(n²): only compare the most-used colors, and
# pixel art does not use more colors than this anyway.
NEAR_DUPLICATE_COLOR_LIMIT = 64
NEAR_DUPLICATE_CHANNEL_DELTA = 8
# Past this color count it is no longer pixel art (photos, noise); fall back to a
# quantized palette and flag the result as approximate.
EXACT_COLOR_LIMIT = 2_000_000


def _bbox(alpha: Image.Image) -> dict | None:
    """Bounding box of everything that is not fully transparent."""
    box = alpha.getbbox()
    if box is None:
        return None
    left, top, right, bottom = box
    return {
        "x": left, "y": top,
        "width": right - left, "height": bottom - top,
    }


def _isolated(alpha: Image.Image) -> int:
    """Pixels with no visible orthogonal neighbour.

    Implemented as four shifted copies OR-ed together: a pixel survives only when the mask is
    set and every neighbour is empty, which is exactly the definition and costs four C-level
    operations instead of four Python lookups per pixel.
    """
    mask = alpha.point(lambda value: 255 if value > 0 else 0, mode="L")
    width, height = mask.size
    padded = Image.new("L", (width + 2, height + 2), 0)
    padded.paste(mask, (1, 1))

    neighbours = Image.new("L", padded.size, 0)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        neighbours = ImageChops.lighter(neighbours, ImageChops.offset(padded, dx, dy))
    neighbours = neighbours.crop((1, 1, width + 1, height + 1))

    # offset() wraps around, but the 1px padding absorbs it: the wrapped values land in the
    # padding column/row, which is then cropped away.
    alone = ImageChops.darker(mask, ImageChops.invert(neighbours))
    return sum(alone.histogram()[1:])


def _near_duplicates(colors: list[tuple[int, ...]],
                     threshold: int = NEAR_DUPLICATE_CHANNEL_DELTA) -> list[list[str]]:
    dupes = []
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            a, b = colors[i], colors[j]
            if all(abs(a[k] - b[k]) <= threshold for k in range(3)):
                if a[3] == b[3]:
                    dupes.append(["#%02X%02X%02X" % a[:3], "#%02X%02X%02X" % b[:3]])
    return dupes


def frame_diff(current_path: Path, previous_path: Path) -> dict:
    """Pixel-exact diff between two exported frames (same size)."""
    current = Image.open(current_path).convert("RGBA")
    previous = Image.open(previous_path).convert("RGBA")
    if current.size != previous.size:
        return {"changed_pixels": None, "bbox": None,
                "error": f"frame sizes differ: {current.size} vs {previous.size}"}
    diff = ImageChops.difference(current, previous)
    # RGBA.getbbox() looks at alpha only; two opaque colours have an alpha difference of 0.
    # Union the RGB and alpha bounds so a colour-only change still gets a real box.
    rgb_box = diff.convert("RGB").getbbox()
    alpha_box = diff.getchannel("A").getbbox()
    boxes = [b for b in (rgb_box, alpha_box) if b is not None]
    if not boxes:
        return {"changed_pixels": 0, "bbox": None}
    bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))
    # The histogram is bounded by the number of distinct RGBA values, not pixels, so this
    # count stays cheap even on a 4096² frame.
    histogram = diff.getcolors(maxcolors=EXACT_COLOR_LIMIT)
    changed = None if histogram is None else sum(
        count for count, color in histogram if color != (0, 0, 0, 0)
    )
    return {
        "changed_pixels": changed,
        "bbox": {"x": bbox[0], "y": bbox[1],
                 "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]},
    }


def _color_stats(img: Image.Image):
    """(visible colors sorted by usage, semi-transparent count, visible pixel count)."""
    histogram = img.getcolors(maxcolors=EXACT_COLOR_LIMIT)
    approximate = False
    if histogram is None:
        # More distinct colors than pixels have palette: not pixel art, and an exact list
        # would cost more than the metrics are worth. Quantize and say so.
        quantized = img.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        histogram = quantized.convert("RGB").getcolors(maxcolors=256) or []
        approximate = True

    visible = [(count, color) for count, color in histogram if color[3] > 0]
    visible.sort(key=lambda item: (-item[0], item[1]))
    semi = sum(count for count, color in histogram if 0 < color[3] < 255)
    return visible, semi, approximate


def compute_metrics(png_path: Path, meta: dict) -> dict:
    img = Image.open(png_path).convert("RGBA")
    width, height = img.size
    alpha = img.getchannel("A")

    visible, semi, approximate = _color_stats(img)
    colors = [color for _, color in visible]
    opaque_count = sum(count for count, _ in visible)

    metrics = {
        "width": width,
        "height": height,
        "color_count": len(colors),
        "palette": ["#%02X%02X%02X" % color[:3] for color in colors],
        "near_duplicate_colors": _near_duplicates(colors[:NEAR_DUPLICATE_COLOR_LIMIT]),
        "bbox": _bbox(alpha),
        "coverage": opaque_count / (width * height),
        "semi_transparent_pixels": semi,
        "isolated_pixels": _isolated(alpha),
        "frame_diffs": [],
    }
    if approximate:
        metrics["palette_approximate"] = True
    return metrics