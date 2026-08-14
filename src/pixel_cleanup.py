"""AI 生成像素画清洗管线（混合管线，docs §12）。

把任意扩散模型/AI 生成器的 PNG 输出，恢复为干净的、可编辑的像素画：
1. 网格恢复：检测整数放大倍率并 nearest 降采样，消除 mixels
2. 剥离 checkerboard 背景
3. 颜色收敛：中位切割量化到 max_colors，或锁定到指定调色板
4. 孤立噪点清除

纯确定性代码，不依赖任何外部模型。清洗结果可用 import_png 导入 Aseprite
继续编辑与动画化。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image as PILImage
except ImportError:  # pragma: no cover - 依赖未安装时降级
    PILImage = None


class PixelCleanupError(RuntimeError):
    """清洗管线错误。"""


@dataclass
class CleanResult:
    """清洗结果报告。"""

    out_path: str
    width: int
    height: int
    scale: int = 1
    colors_before: int = 0
    colors_after: int = 0
    stripped_checker: bool = False
    checker_pixels: int = 0
    despeckled: int = 0
    palette_locked: bool = False
    max_colors: Optional[int] = None
    warnings: List[str] = field(default_factory=list)


def _require_pil():
    if PILImage is None:  # pragma: no cover
        raise PixelCleanupError(
            "Pillow is required for image cleanup. Install with: pip install pillow"
        )


def parse_palette(palette: str) -> List[str]:
    """解析调色板字符串为 #RRGGBB 大写列表。

    Args:
        palette: 逗号或空格分隔的十六进制颜色，如 "#FF0000,#00FF00"

    Returns:
        规范化的颜色列表；空输入返回空列表

    Raises:
        PixelCleanupError: 包含非法颜色格式时
    """
    result = []
    for part in palette.replace(",", " ").split():
        part = part.strip().upper()
        if not part.startswith("#"):
            part = "#" + part
        if len(part) != 7 or any(c not in "0123456789ABCDEF" for c in part[1:]):
            raise PixelCleanupError(f"Invalid palette color: {part!r}")
        result.append(part)
    return result


def detect_scale(img, max_scale: int = 16) -> int:
    """检测图像是否为整数放大倍率的像素画。

    对每个候选倍率 s：nearest 降采样到 1/s 再升采样回原尺寸，
    若无损往返则说明原图是 s 倍 NN 放大。返回最大有效倍率，否则 1。

    Args:
        img: PIL RGBA 图像
        max_scale: 最大检测倍率

    Returns:
        检测到的整数放大倍率（>=1）
    """
    w, h = img.size
    for s in range(min(max_scale, w // 4, h // 4), 1, -1):
        if w % s != 0 or h % s != 0:
            continue
        small = img.resize((w // s, h // s), PILImage.NEAREST)
        back = small.resize((w, h), PILImage.NEAREST)
        # 纯色/单色图在任何倍率下都能无损往返，需排除
        colors = small.getcolors(10 ** 7)
        if colors is None or len(colors) < 2:
            continue
        if back.tobytes() == img.tobytes():
            return s
    return 1


def strip_checkerboard(img, threshold: float = 0.15):
    """剥离烘焙的棋盘格背景（AI 生成图常见）。

    检测规则：若 (0,0) 与 (1,0) 颜色不同，且"奇偶格颜色恒为对应色"的像素
    占比超过 threshold，则判定为棋盘格背景，将这些像素置为透明。

    Args:
        img: PIL RGBA 图像（原地修改）
        threshold: 判定占比阈值

    Returns:
        (是否检测到, 剥离像素数)
    """
    w, h = img.size
    c00 = img.getpixel((0, 0))
    c10 = img.getpixel((1, 0))
    if c00 == c10:
        return False, 0

    matches = 0
    total = w * h
    # 只采样前若干行加速（棋盘格通常遍布全图）
    sample_h = min(h, 64)
    for y in range(sample_h):
        for x in range(w):
            parity = (x + y) % 2
            c = img.getpixel((x, y))
            expected = c00 if parity == 0 else c10
            if c == expected:
                matches += 1

    if sample_h > 0 and matches / (sample_h * w) >= threshold:
        stripped = 0
        for y in range(h):
            for x in range(w):
                parity = (x + y) % 2
                expected = c00 if parity == 0 else c10
                if img.getpixel((x, y)) == expected:
                    img.putpixel((x, y), (0, 0, 0, 0))
                    stripped += 1
        return True, stripped
    return False, 0


def _hex_to_rgb(hex_color: str):
    return (
        int(hex_color[1:3], 16),
        int(hex_color[3:5], 16),
        int(hex_color[5:7], 16),
    )


def lock_to_palette(img, palette: List[str]) -> None:
    """把每个不透明像素吸附到最近调色板颜色（原地修改）。

    跨素材一致性关键：所有资产共用一套颜色词汇，整个角色集合看起来像一个游戏。

    Args:
        img: PIL RGBA 图像
        palette: #RRGGBB 颜色列表
    """
    colors = [_hex_to_rgb(c) for c in palette]
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = img.getpixel((x, y))
            if a == 0:
                continue
            best, best_d = colors[0], 1 << 30
            for cr, cg, cb in colors:
                d = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2
                if d < best_d:
                    best_d, best = d, (cr, cg, cb)
            img.putpixel((x, y), (best[0], best[1], best[2], a))


def quantize_colors(img, max_colors: int) -> None:
    """中位切割量化不透明像素到 max_colors（原地修改）。

    Args:
        img: PIL RGBA 图像
        max_colors: 目标颜色数（1-256）
    """
    if max_colors < 1:
        raise PixelCleanupError("max_colors must be >= 1")
    max_colors = min(256, max_colors)
    alpha = img.getchannel("A")
    rgb = img.convert("RGB")
    q = rgb.quantize(colors=max_colors, method=PILImage.Quantize.MEDIANCUT)
    q = q.convert("RGB").convert("RGBA")
    q.putalpha(alpha)
    img.paste(q)


def despeckle(img) -> int:
    """清除孤立噪点：不透明像素若与 8 邻域全部不同色则清除（原地修改）。

    处理两类：邻域全透明 → 变透明；邻域有不透明像素 → 取邻域多数色填充。

    Args:
        img: PIL RGBA 图像

    Returns:
        清除的像素数
    """
    w, h = img.size
    px = img.load()
    original = [img.crop((0, 0, w, h))]
    src = original[0].load()
    removed = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a == 0:
                continue
            same, opaque_neighbors = 0, []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        nr, ng, nb, na = src[nx, ny]
                        if na > 0:
                            opaque_neighbors.append((nr, ng, nb))
                            if (nr, ng, nb) == (r, g, b):
                                same += 1
            if same > 0:
                continue
            if not opaque_neighbors:
                px[x, y] = (0, 0, 0, 0)
            else:
                majority = max(set(opaque_neighbors), key=opaque_neighbors.count)
                px[x, y] = (majority[0], majority[1], majority[2], a)
            removed += 1
    return removed


def count_colors(img) -> int:
    """统计不透明像素的颜色种数。"""
    return len({
        img.getpixel((x, y))
        for y in range(img.height)
        for x in range(img.width)
        if img.getpixel((x, y))[3] > 0
    })


def clean_image_file(
    src_path: str,
    out_path: str,
    max_colors: Optional[int] = None,
    palette: str = "",
    strip_background: bool = True,
    force_scale: int = 0,
    do_despeckle: bool = True,
) -> CleanResult:
    """清洗一张 AI 生成图。

    Args:
        src_path: 输入 PNG 路径
        out_path: 输出 PNG 路径
        max_colors: 目标颜色数（None=不量化）
        palette: 锁定调色板字符串（优先于 max_colors）
        strip_background: 是否剥离棋盘格背景（默认 True）
        force_scale: 强制缩放倍率（0=自动检测）
        do_despeckle: 是否清除孤立噪点（默认 True）

    Returns:
        CleanResult 报告

    Raises:
        PixelCleanupError: 输入不存在或格式不支持时
    """
    _require_pil()
    src = Path(src_path)
    if not src.exists():
        raise PixelCleanupError(f"Image not found: {src_path}")

    try:
        img = PILImage.open(src)
        img.load()
    except Exception as e:
        raise PixelCleanupError(f"Failed to open image: {e}") from e
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    result = CleanResult(out_path=out_path, width=img.width, height=img.height)

    # 1. 网格恢复
    detected = detect_scale(img)
    scale = force_scale if force_scale >= 1 else detected
    if scale > 1:
        img = img.resize((img.width // scale, img.height // scale), PILImage.NEAREST)
        result.scale = scale
        result.width, result.height = img.size

    # 2. 剥离棋盘格背景
    if strip_background:
        stripped, count = strip_checkerboard(img)
        result.stripped_checker = stripped
        result.checker_pixels = count

    result.colors_before = count_colors(img)

    # 3. 颜色收敛（调色板锁定优先）
    if palette.strip():
        pal = parse_palette(palette)
        if pal:
            lock_to_palette(img, pal)
            result.palette_locked = True
            result.max_colors = len(pal)
    elif max_colors and max_colors > 0:
        quantize_colors(img, max_colors)
        result.max_colors = max_colors

    result.colors_after = count_colors(img)

    # 4. 去噪
    if do_despeckle:
        result.despeckled = despeckle(img)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
    return result


def ensure_pillow_available():
    """确保 Pillow 可用（供工具层调用并给出友好报错）。"""
    _require_pil()
    return os.path.dirname(os.path.dirname(__file__))
