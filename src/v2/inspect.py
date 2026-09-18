"""感知指标：从导出的 PNG + Lua 元数据计算（spec §8）。"""

from collections import Counter
from pathlib import Path

from PIL import Image


def _bbox(pixels, width, height):
    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > 0:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return {
        "x": min(xs),
        "y": min(ys),
        "width": max(xs) - min(xs) + 1,
        "height": max(ys) - min(ys) + 1,
    }


def _isolated(pixels, width, height) -> int:
    count = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] == 0:
                continue
            neighbors = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and pixels[nx, ny][3] > 0:
                    neighbors += 1
            if neighbors == 0:
                count += 1
    return count


def _near_duplicates(colors: list[tuple[int, ...]], threshold: int = 8) -> list[list[str]]:
    dupes = []
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            a, b = colors[i], colors[j]
            if all(abs(a[k] - b[k]) <= threshold for k in range(3)):
                if a[3] == b[3]:
                    dupes.append(["#%02X%02X%02X" % a[:3], "#%02X%02X%02X" % b[:3]])
    return dupes


def compute_metrics(png_path: Path, meta: dict) -> dict:
    img = Image.open(png_path).convert("RGBA")
    width, height = img.size
    pixels = img.load()
    histogram = Counter(pixels[x, y] for y in range(height) for x in range(width))
    opaque = {c: n for c, n in histogram.items() if c[3] > 0}
    colors = list(opaque)
    semi = sum(n for c, n in histogram.items() if 0 < c[3] < 255)
    opaque_count = sum(n for c, n in opaque.items())
    return {
        "width": width,
        "height": height,
        "color_count": len(opaque),
        "palette": ["#%02X%02X%02X" % c[:3] for c in colors],
        "near_duplicate_colors": _near_duplicates(colors),
        "bbox": _bbox(pixels, width, height),
        "coverage": opaque_count / (width * height),
        "semi_transparent_pixels": semi,
        "isolated_pixels": _isolated(pixels, width, height),
        "grid_offset": {"x": 0, "y": 0},
        "frame_diffs": [],
    }
