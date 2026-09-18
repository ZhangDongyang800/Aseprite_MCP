"""像素画清洗管线测试（混合管线，docs §12）。

用合成图像验证：网格恢复（去 mixels）、棋盘格剥离、调色板锁定、
颜色量化、孤立噪点清除、端到端 clean_image_file。
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.pixel_cleanup import (
    PixelCleanupError,
    clean_image_file,
    count_colors,
    despeckle,
    detect_scale,
    lock_to_palette,
    parse_palette,
    quantize_colors,
    strip_checkerboard,
)
from PIL import Image as PILImage


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _solid(size, color):
    img = PILImage.new("RGBA", size, color)
    return img


def test_parse_palette_normalizes_colors():
    """测试调色板字符串解析：大小写归一、补 #、分隔符兼容。"""
    pal = parse_palette("#ff0000, 00ff00 0000ff")
    assert pal == ["#FF0000", "#00FF00", "#0000FF"]


def test_parse_palette_empty():
    """测试空字符串返回空列表。"""
    assert parse_palette("") == []
    assert parse_palette("   ") == []


def test_parse_palette_invalid():
    """测试非法颜色格式抛出异常。"""
    with pytest.raises(PixelCleanupError):
        parse_palette("#GGGGGG")


# ═══════════════════════════════════════════
# 网格恢复
# ═══════════════════════════════════════════

def test_detect_scale_no_upscale():
    """测试原始像素画（1 倍）检测为 1。"""
    img = _solid((16, 16), (255, 0, 0, 255))
    assert detect_scale(img) == 1


def test_detect_scale_detects_4x_upscale():
    """测试 4 倍 NN 放大图像检测为 4。"""
    base = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    base.putpixel((2, 2), (255, 0, 0, 255))
    base.putpixel((5, 6), (0, 255, 0, 255))
    up = base.resize((32, 32), PILImage.NEAREST)
    assert detect_scale(up) == 4


def test_detect_scale_resists_resampled_upscale():
    """测试非整数重采样图（BILINEAR）不被误判为大倍率。"""
    base = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    base.putpixel((2, 2), (255, 0, 0, 255))
    base.putpixel((5, 6), (0, 255, 0, 255))
    up = base.resize((32, 32), PILImage.BILINEAR)
    assert detect_scale(up) == 1


# ═══════════════════════════════════════════
# 棋盘格剥离
# ═══════════════════════════════════════════

def _checker_image(size, c0, c1, sprite_color=None):
    img = PILImage.new("RGBA", size, (0, 0, 0, 0))
    w, h = size
    for y in range(h):
        for x in range(w):
            img.putpixel((x, y), c0 if (x + y) % 2 == 0 else c1)
    if sprite_color:  # 中心画一个精灵色块
        for y in range(h // 4, 3 * h // 4):
            for x in range(w // 4, 3 * w // 4):
                img.putpixel((x, y), sprite_color)
    return img


def test_strip_checkerboard_detects_and_strips():
    """测试棋盘格背景被检测并置为透明。"""
    img = _checker_image((16, 16), (128, 128, 128, 255), (64, 64, 64, 255))
    stripped, count = strip_checkerboard(img)
    assert stripped is True
    assert count > 0
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)
    assert img.getpixel((1, 0)) == (0, 0, 0, 0)


def test_strip_checkerboard_keeps_sprite():
    """测试中央精灵像素不被误删。"""
    img = _checker_image(
        (16, 16), (128, 128, 128, 255), (64, 64, 64, 255),
        sprite_color=(255, 0, 0, 255),
    )
    stripped, _ = strip_checkerboard(img)
    assert stripped is True
    assert img.getpixel((8, 8)) == (255, 0, 0, 255)


def test_strip_checkerboard_solid_background_noop():
    """测试纯色背景不被误判为棋盘格。"""
    img = _solid((16, 16), (100, 100, 100, 255))
    stripped, count = strip_checkerboard(img)
    assert stripped is False
    assert count == 0


# ═══════════════════════════════════════════
# 颜色收敛
# ═══════════════════════════════════════════

def test_lock_to_palette_snaps_all_pixels():
    """测试所有不透明像素吸附到最近调色板色。"""
    img = PILImage.new("RGBA", (4, 4), (0, 0, 0, 0))
    img.putpixel((0, 0), (250, 5, 5, 255))
    img.putpixel((1, 0), (2, 250, 3, 255))
    img.putpixel((2, 0), (10, 8, 12, 128))  # 半透明也吸附
    img.putpixel((3, 0), (0, 0, 0, 0))       # 透明不吸附

    lock_to_palette(img, ["#FF0000", "#00FF00"])

    assert img.getpixel((0, 0)) == (255, 0, 0, 255)
    assert img.getpixel((1, 0)) == (0, 255, 0, 255)
    assert img.getpixel((2, 0)) == (255, 0, 0, 128)
    assert img.getpixel((3, 0)) == (0, 0, 0, 0)


def test_quantize_colors_reduces_count():
    """测试量化后颜色数不超过目标。"""
    img = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    colors = [
        (255, 0, 0, 255), (254, 1, 0, 255), (253, 2, 0, 255),
        (0, 255, 0, 255), (0, 254, 1, 255), (0, 0, 255, 255),
        (0, 0, 254, 255), (0, 0, 253, 255),
    ]
    for i, c in enumerate(colors):
        img.putpixel((i, 0), c)

    quantize_colors(img, 4)

    assert count_colors(img) <= 4


def test_quantize_colors_invalid_count():
    """测试非法颜色数抛出异常。"""
    with pytest.raises(PixelCleanupError):
        quantize_colors(PILImage.new("RGBA", (4, 4)), 0)


# ═══════════════════════════════════════════
# 去噪
# ═══════════════════════════════════════════

def test_despeckle_removes_isolated_pixel():
    """测试完全孤立的单像素被清除。"""
    img = PILImage.new("RGBA", (5, 5), (0, 0, 0, 0))
    img.putpixel((2, 2), (255, 0, 0, 255))
    removed = despeckle(img)
    assert removed == 1
    assert img.getpixel((2, 2)) == (0, 0, 0, 0)


def test_despeckle_keeps_grouped_pixels():
    """测试成组像素（2 邻接）不被清除。"""
    img = PILImage.new("RGBA", (5, 5), (0, 0, 0, 0))
    img.putpixel((2, 2), (255, 0, 0, 255))
    img.putpixel((2, 3), (255, 0, 0, 255))
    removed = despeckle(img)
    assert removed == 0


def test_despeckle_fills_hole_with_majority():
    """测试孤立像素填入邻域多数色（连通性修复）。"""
    img = PILImage.new("RGBA", (5, 5), (0, 0, 0, 0))
    for y in (1, 3):
        for x in (1, 2, 3):
            img.putpixel((x, y), (0, 255, 0, 255))
    img.putpixel((2, 2), (255, 0, 0, 255))  # 绿环中心的孤立红点
    removed = despeckle(img)
    assert removed == 1
    assert img.getpixel((2, 2)) == (0, 255, 0, 255)


# ═══════════════════════════════════════════
# 端到端
# ═══════════════════════════════════════════

def test_clean_image_file_end_to_end(tmp_path):
    """测试完整管线：4x 放大 + 棋盘格 + 多色 → 清洗。"""
    # 构造 8x8 脏图
    base = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y in range(8):
        for x in range(8):
            base.putpixel((x, y), (128, 128, 128, 255) if (x + y) % 2 == 0 else (64, 64, 64, 255))
    base.putpixel((3, 3), (255, 0, 0, 255))
    base.putpixel((4, 4), (254, 1, 0, 255))
    dirty = base.resize((32, 32), PILImage.NEAREST)

    src = tmp_path / "dirty.png"
    out = tmp_path / "clean.png"
    dirty.save(src)

    result = clean_image_file(
        src_path=str(src),
        out_path=str(out),
        max_colors=8,
        strip_background=True,
    )

    assert result.scale == 4
    assert result.width == 8 and result.height == 8
    assert result.stripped_checker is True
    assert out.exists()

    cleaned = PILImage.open(out).convert("RGBA")
    # 背景棋盘被剥离 → 四角全透明
    assert cleaned.getpixel((0, 0))[3] == 0
    # 精灵像素保留
    assert cleaned.getpixel((3, 3))[3] == 255


def test_clean_image_file_palette_lock(tmp_path):
    """测试调色板锁定：所有像素落在给定调色板内。"""
    img = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    img.putpixel((1, 1), (240, 10, 10, 255))
    img.putpixel((2, 2), (10, 240, 10, 255))

    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    img.save(src)

    result = clean_image_file(
        src_path=str(src),
        out_path=str(out),
        palette="#FF0000,#00FF00",
        force_scale=1,  # 禁用自动降采样，保持 8x8
        do_despeckle=False,  # 单像素孤立点会被 despeckle 合并，本测试只验证锁色
    )

    assert result.palette_locked is True
    assert result.colors_after == 2
    cleaned = PILImage.open(out).convert("RGBA")
    assert cleaned.getpixel((1, 1)) == (255, 0, 0, 255)
    assert cleaned.getpixel((2, 2)) == (0, 255, 0, 255)


def test_clean_image_file_missing_file(tmp_path):
    """测试输入文件不存在时抛出异常。"""
    with pytest.raises(PixelCleanupError, match="not found"):
        clean_image_file(
            src_path=str(tmp_path / "nope.png"),
            out_path=str(tmp_path / "out.png"),
        )
