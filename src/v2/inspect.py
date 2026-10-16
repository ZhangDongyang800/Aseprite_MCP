"""感知指标：从导出的 PNG + Lua 元数据计算（spec §8）。

指标全部走 PIL 的 C 实现：逐像素的 Python 循环会让 2048² 画布的单次 inspect 从毫秒级
掉到十几秒，而"画完看一眼"是这个工具最频繁的调用。
"""

from pathlib import Path

from PIL import Image, ImageChops

# 近重复色两两比较是 O(n²)：只对最常用的这些颜色做比较，像素画本来也用不了更多颜色。
NEAR_DUPLICATE_COLOR_LIMIT = 64
NEAR_DUPLICATE_CHANNEL_DELTA = 8
# 超过这个颜色数就不是像素画了（照片、噪点），此时退回量化调色板并标记为近似。
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
        "grid_offset": {"x": 0, "y": 0},
        "frame_diffs": [],
    }
    if approximate:
        metrics["palette_approximate"] = True
    return metrics