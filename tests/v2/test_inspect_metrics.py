"""inspect metrics: exact results, and fast enough to sit in a draw->look loop."""

import time

from PIL import Image as PILImage

from src.v2.inspect import compute_metrics

META = {"width": 0, "height": 0, "frames": [], "layers": []}


def _save(img, tmp_path, name="m.png"):
    p = tmp_path / name
    img.save(p)
    return p


def test_metrics_on_a_full_2048_canvas_stay_interactive(tmp_path):
    """A per-pixel Python loop made this take tens of seconds on big canvases."""
    img = PILImage.new("RGBA", (2048, 2048), (20, 40, 60, 255))
    p = _save(img, tmp_path)

    started = time.perf_counter()
    m = compute_metrics(p, dict(META))
    elapsed = time.perf_counter() - started

    assert m["coverage"] == 1.0
    assert m["color_count"] == 1
    assert elapsed < 5.0, f"metrics took {elapsed:.1f}s on a 2048x2048 canvas"


def test_isolated_pixel_count_is_exact(tmp_path):
    img = PILImage.new("RGBA", (5, 5), (0, 0, 0, 0))
    for x in range(3):          # a horizontal run: none of these are isolated
        img.putpixel((x, 0), (255, 0, 0, 255))
    img.putpixel((4, 4), (0, 0, 255, 255))   # alone
    img.putpixel((0, 4), (0, 255, 0, 255))   # alone
    p = _save(img, tmp_path, "iso.png")

    m = compute_metrics(p, dict(META))

    assert m["isolated_pixels"] == 2
    assert m["bbox"] == {"x": 0, "y": 0, "width": 5, "height": 5}


def test_bbox_tracks_only_visible_pixels(tmp_path):
    img = PILImage.new("RGBA", (10, 10), (0, 0, 0, 0))
    img.putpixel((3, 4), (255, 255, 255, 255))
    img.putpixel((6, 8), (255, 255, 255, 255))
    p = _save(img, tmp_path, "bbox.png")

    m = compute_metrics(p, dict(META))

    assert m["bbox"] == {"x": 3, "y": 4, "width": 4, "height": 5}


def test_palette_is_ordered_by_usage(tmp_path):
    img = PILImage.new("RGBA", (4, 4), (0, 0, 0, 0))
    img.putpixel((0, 0), (1, 1, 1, 255))      # used once
    for x in (1, 2, 3):
        img.putpixel((x, 0), (9, 9, 9, 255))  # used three times
    p = _save(img, tmp_path, "pal.png")

    m = compute_metrics(p, dict(META))

    assert m["color_count"] == 2
    assert m["palette"][0] == "#090909"


def test_semi_transparent_pixels_are_counted_separately(tmp_path):
    img = PILImage.new("RGBA", (3, 3), (0, 0, 0, 0))
    img.paste((10, 10, 10, 128), (0, 0, 3, 3))
    p = _save(img, tmp_path, "semi.png")

    m = compute_metrics(p, dict(META))

    assert m["semi_transparent_pixels"] == 9
    assert m["coverage"] == 1.0