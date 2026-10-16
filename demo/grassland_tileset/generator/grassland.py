"""草原 tileset 的像素美术定义（纯 Python，确定性生成）。

专业 tileset 的几条硬规矩，这里都按规矩来：
- **过渡砖**：路径/水域/麦田与草地、沙地相接处必须有专门的过渡瓦片
  （`*_edge_*`、`*_corner_*`），否则拼出来就是硬边方块，专业感全无；
- **平铺无缝**：所有纹理由 (x, y) 的哈希决定，没有依赖边界条件的画法；
- **光源左上**：亮面一律在左上侧，暗面在右下侧；
- **克制的噪点**：草地用 2x2 色块抖动、水面用 1px 断续短划，都刻意压密度，
  否则 32px 瓦片大面积铺开时就是一片雪花；
- **同一套调色板**：全套 32 张瓦片共用 26 色，色相与明度层级统一。

对外暴露：TILE_NAMES（32 张瓦片的固定槽位顺序）、tile_matrix(name, phase)、
sheet_frame(phase)（图集一帧，水面随相位变化）、scene()（拼好的示例场景）。
produce.py 负责把它们送进 Aseprite 并逐像素校验。
"""

from __future__ import annotations

TILE = 32
SHEET_COLS = 8
SHEET_ROWS = 4
SCENE_COLS = 12
SCENE_ROWS = 8
WATER_PHASES = 4

PAL: dict[str, str] = {
    # 草（明度四级）
    "g": "#4E8C3F", "G": "#417A36", "l": "#5DA349", "L": "#6FBB57", "d": "#2F5D2A",
    # 泥土 / 路
    "e": "#8B6647", "E": "#7A5940", "f": "#A07D5B", "F": "#B99170",
    # 水
    "w": "#3E7BB6", "W": "#2F6093", "r": "#6FB3DE", "R": "#B9E2F5",
    # 沙
    "s": "#D9C08A", "S": "#C2A672", "t": "#EBD9AE",
    # 石
    "o": "#7A7E86", "O": "#5E626A", "q": "#9AA0A8", "Q": "#C2C7CE",
    # 木
    "b": "#6B4A2F", "B": "#4A3220", "c": "#8A6240",
    # 麦
    "y": "#D9B45B", "Y": "#B9913C", "z": "#EFD98E",
    # 点缀
    "p": "#F2EEF8", "h": "#F0C860", "m": "#E0708F", "k": "#C8503F", "n": "#EFE3D0",
}


def _hash(x: int, y: int, salt: int = 0) -> int:
    n = (x * 374761393 + y * 668265263 + salt * 2246822519) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFFFFFFFF


def blank(w: int = TILE, h: int | None = None) -> list[list[str]]:
    return [["." for _ in range(w)] for _ in range(h if h is not None else w)]


def _put(grid, x, y, code):
    if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
        grid[y][x] = code


# --------------------------------------------------------------------- 草

def _grass_base(salt: int = 1, light: bool = False) -> list[list[str]]:
    """草地：2x2 色块抖动 + 稀疏草叶，避免逐像素噪点造成的"雪花感"。"""
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            v = _hash(x >> 1, y >> 1, salt) % 16
            if light:
                grid[y][x] = "l" if v < 6 else ("g" if v < 13 else "L")
            else:
                grid[y][x] = "G" if v < 4 else ("g" if v < 12 else "l")
    for y in range(TILE):
        for x in range(TILE):
            if _hash(x, y, salt + 7) % 89 == 0:          # 单根高光草叶
                _put(grid, x, y, "L")
                _put(grid, x, y + 1, "l")
    return grid


def _tuft(grid, cx, base_y, tall=10, spread=3):
    """一簇草：根部压深、中间高、左侧受光——否则会和底色糊在一起。"""
    for dx in range(-spread - 1, spread + 2):
        _put(grid, cx + dx, base_y, "G")            # 根部阴影
    for dx in range(-spread, spread + 1):
        hgt = tall - abs(dx) * 2
        for dy in range(hgt):
            if dy < hgt * 0.35:
                code = "l"
            elif dx <= 0:
                code = "L"
            else:
                code = "G"
            _put(grid, cx + dx, base_y - dy, code)
        _put(grid, cx + dx, base_y - hgt + 1, "l")


def tile_grass() -> list[list[str]]:
    grid = _grass_base()
    for cx, by in ((7, 26), (21, 29), (26, 22)):
        _tuft(grid, cx, by, 8, 2)
    return grid


def tile_grass_light() -> list[list[str]]:
    """被太阳照到的一块：同材质、更亮的色阶，用于场景里打散重复感。"""
    grid = _grass_base(light=True)
    for cx, by in ((12, 27), (25, 24)):
        _tuft(grid, cx, by, 7, 2)
    return grid


def tile_grass_tuft() -> list[list[str]]:
    grid = _grass_base()
    _tuft(grid, 10, 30, 14, 4)
    _tuft(grid, 23, 28, 11, 3)
    return grid


def tile_grass_flowers() -> list[list[str]]:
    """花丛：三朵能一眼认出的花（白/黄/粉），带花茎与高光。"""
    grid = _grass_base()
    for cx, by, petal in ((7, 22, "p"), (21, 26, "h"), (14, 17, "m"), (26, 14, "p")):
        for y in range(by - 4, by + 1):                 # 花茎
            _put(grid, cx, y, "G")
        _put(grid, cx, by, "G")
        for dx in (-1, 0, 1):                            # 花瓣
            _put(grid, cx + dx, by - 5, petal)
            _put(grid, cx + dx, by - 7, petal)
        _put(grid, cx, by - 6, "R" if petal == "p" else "t")
    return grid


def tile_bush() -> list[list[str]]:
    grid = _grass_base()
    blobs = [(16, 19, 11), (9, 23, 7), (23, 23, 7)]
    for y in range(TILE):
        for x in range(TILE):
            for bx, by, br in blobs:
                if ((x - bx) * 1.0) ** 2 + ((y - by) * 1.22) ** 2 <= br * br:
                    lit = (x < 16 and y < 19) or (x - 16 + y - 19) < -6
                    v = _hash(x >> 1, y >> 1, 9) % 10
                    grid[y][x] = "L" if lit and v < 5 else ("l" if lit else ("d" if v < 4 else "g"))
                    break
    for x in range(5, 28):                               # 脚下投影
        if _hash(x, 0, 10) % 2 == 0:
            _put(grid, x, 30, "G")
    return grid


# --------------------------------------------------------------------- 路径与过渡

def tile_path() -> list[list[str]]:
    """夯土路：两大色阶 + 少量碎石，避免满屏噪点。"""
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            v = _hash(x >> 1, y >> 1, 11) % 12
            grid[y][x] = "E" if v < 4 else "e"
    for y in range(TILE):
        for x in range(TILE):
            if _hash(x, y, 12) % 211 == 0:
                _put(grid, x, y, "F")
                _put(grid, x + 1, y, "f")
    return grid


def _edge_tile(base: list[list[str]], neighbor: list[list[str]], side: str,
               salt: int, inset: int = 11) -> list[list[str]]:
    """在 base 上沿 side 方向切出一条抖动边界，并把 neighbor 的材质渐入过来。

    `side` 指邻居材质所在的那条边：n=上、s=下、w=左、e=右。
    最后两格用棋盘抖动过渡（而不是硬切），这是像素风里让边缘"接得住"的关键。
    """
    grid = [row[:] for row in base]
    blend = 2

    def toward(t: int) -> tuple[int, int]:
        """从边界往外第 t 格的坐标（沿边界方向为 i）。"""
        if side == "n":
            return inset_of(i) - t, i
        if side == "s":
            return TILE - 1 - inset_of(i) + t, i
        if side == "w":
            return i, inset_of(i) - t
        return i, TILE - 1 - inset_of(i) + t

    def inset_of(i: int) -> int:
        return inset + _hash(i, 0, salt) % 4

    for i in range(TILE):
        for t in range(blend + 3):
            y, x = toward(t)
            if not (0 <= y < TILE and 0 <= x < TILE):
                continue
            if t < 2:
                grid[y][x] = neighbor[y][x]
            elif t < blend + 2:
                grid[y][x] = neighbor[y][x] if (i + y) % 2 == 0 else base[y][x]
            else:
                grid[y][x] = base[y][x] if (i + y) % 2 == 0 else neighbor[y][x]
    return grid


def _path_edge(side: str, salt: int) -> list[list[str]]:
    grid = _edge_tile(tile_path(), _grass_base(), side, salt)
    for i in range(TILE):                                  # 边界上探出的草叶（短、稀，别抢戏）
        pos = 11 + _hash(i, 0, salt) % 4
        if _hash(i, 0, salt + 1) % 5 == 0:
            if side == "n":
                for t in range(3):
                    _put(grid, i, pos + t, "g" if t else "l")
            elif side == "s":
                for t in range(3):
                    _put(grid, i, pos - t, "g" if t else "l")
            elif side == "w":
                for t in range(3):
                    _put(grid, pos + t, i, "g" if t else "l")
            else:
                for t in range(3):
                    _put(grid, pos - t, i, "g" if t else "l")
    return grid


# --------------------------------------------------------------------- 水与沙岸

def _water(phase: int) -> list[list[str]]:
    """水面：稀疏的断续波纹。

    整行铺亮色会让大片水域变成条纹布，所以每条波纹只有 1px 高，并被哈希打断成
    4-8px 的短划；再加一点点浪尖高光和深水暗纹，靠对比而不是靠密度取胜。
    """
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            grid[y][x] = "W" if y > TILE * 0.68 else "w"
    for band in range(TILE // 7 + 1):
        yy = (band * 7 + phase * 2) % TILE
        for x in range(TILE):
            if _hash(x >> 2, yy >> 1, 41) % 3:
                continue
            grid[yy][x] = "r"
        if _hash(band, 0, 44) % 2 == 0:
            for x in range(TILE):
                if _hash(x >> 2, yy >> 1, 42) % 6 == 0:
                    grid[(yy + 1) % TILE][x] = "R"
    for y in range(int(TILE * 0.7), TILE):                 # 深处再压一点暗纹
        for x in range(TILE):
            if _hash(x >> 2, y >> 1, 43) % 8 == 0:
                grid[y][x] = "W"
    return grid


def _sand_base() -> list[list[str]]:
    """沙：两大色阶 + 极少高光，沙地越安静，水陆交界越干净。"""
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            v = _hash(x >> 1, y >> 1, 51) % 12
            grid[y][x] = "S" if v < 4 else "s"
    for y in range(TILE):
        for x in range(TILE):
            if _hash(x, y, 54) % 241 == 0:
                _put(grid, x, y, "t")
    return grid


def _water_edge(side: str, salt: int, phase: int) -> list[list[str]]:
    """水域过渡砖：实心沙带 -> 两色抖动 -> 边界上一条断续浪花。

    `side` 指沙所在的那条边（n=上、s=下、w=左、e=右）。不用通用的棋盘抖动：
    沙和水互相对抖会产生橙蓝高频噪点，看着像脏边而不是沙滩。
    """
    sand, water = _sand_base(), _water(phase)
    grid = [row[:] for row in water]
    solid, blend = 3, 3

    def toward(i: int, t: int) -> tuple[int, int]:
        pos = 11 + _hash(i, 0, salt) % 3
        if side == "n":
            return pos - t, i
        if side == "s":
            return pos + t, i
        if side == "w":
            return i, pos - t
        return i, pos + t

    for i in range(TILE):
        for t in range(solid + blend + 1):
            y, x = toward(i, t)
            if not (0 <= y < TILE and 0 <= x < TILE):
                continue
            if t < solid:
                grid[y][x] = sand[y][x]
            elif t < solid + blend - 1:
                grid[y][x] = sand[y][x] if (i + t) % 2 == 0 else "S"
            else:
                grid[y][x] = sand[y][x] if (i + t) % 4 == 0 else water[y][x]
        y, x = toward(i, 0)                                # 浪花线：留缺口，别连成一条白线
        foam = "R" if _hash(i, 0, salt + 2) % 6 else "r"
        if 0 <= y < TILE and 0 <= x < TILE:
            grid[y][x] = foam
        y, x = toward(i, 1)
        if 0 <= y < TILE and 0 <= x < TILE and _hash(i, 1, salt + 3) % 2 == 0:
            grid[y][x] = "r"
    return grid


def _water_corner(corner: str, salt: int, phase: int) -> list[list[str]]:
    """水域转角：象限圆弧过渡（沙在水之外），拼起来池塘边缘才是圆的。

    `corner` 指水域所在的那个象限（nw = 水在左上角），沙在象限外侧。
    """
    sand, water = _sand_base(), _water(phase)
    grid = blank()
    flip_x = corner in ("ne", "se")
    flip_y = corner in ("sw", "se")
    off = TILE - 13
    for y in range(TILE):
        for x in range(TILE):
            dx = (TILE - 1 - x if flip_x else x) - off
            dy = (TILE - 1 - y if flip_y else y) - off
            dist = (dx * dx + dy * dy) ** 0.5
            r = 17 + _hash(x, y, salt) % 4
            grid[y][x] = water[y][x] if dist < r - 1 else sand[y][x]
            if r - 1 <= dist < r + 1:
                grid[y][x] = water[y][x] if (x + y) % 2 == 0 else sand[y][x]
            elif r <= dist < r + 3 and _hash(x, y, salt + 1) % 2 == 0:
                grid[y][x] = "S"
    return grid


def _path_corner(corner: str, salt: int) -> list[list[str]]:
    """路径转角：路面在象限内侧，草在象限外侧。"""
    path, grass = tile_path(), _grass_base()
    grid = blank()
    flip_x = corner in ("ne", "se")
    flip_y = corner in ("sw", "se")
    off = TILE - 13
    for y in range(TILE):
        for x in range(TILE):
            dx = (TILE - 1 - x if flip_x else x) - off
            dy = (TILE - 1 - y if flip_y else y) - off
            dist = (dx * dx + dy * dy) ** 0.5
            r = 15 + _hash(x, y, salt) % 4
            grid[y][x] = path[y][x] if dist < r else grass[y][x]
            if r - 1 <= dist < r:
                grid[y][x] = path[y][x]          # 1px 硬边比 2px 噪点环更干净
    return grid


def tile_reeds(phase: int = 1) -> list[list[str]]:
    """浅水芦苇：细杆 + 顶端深色穗，成丛出现（穗子用草色，别用麦色）。"""
    grid = _water(phase)
    for cx, by in ((6, 30), (14, 31), (23, 29), (28, 31)):
        top = by - 14 - (_hash(cx, 0, 61) % 5)
        for y in range(top, by):
            _put(grid, cx, y, "g" if y < by - 5 else "G")
        for dy in range(5):
            _put(grid, cx, top + dy, "d" if dy % 2 else "G")
        _put(grid, cx + 1, top + 2, "G")
        _put(grid, cx - 1, top + 3, "G")
    return grid


# --------------------------------------------------------------------- 石木杂项

def tile_rock() -> list[list[str]]:
    grid = _grass_base()
    cx, cy = 16, 21
    for y in range(TILE):
        for x in range(TILE):
            dx, dy = (x - cx) / 11.0, (y - cy) / 8.0
            if dx * dx + dy * dy <= 1.0:
                v = _hash(x >> 1, y >> 1, 71) % 6
                if (x < cx and y < cy) or (x - cx + y - cy) < -7:
                    grid[y][x] = "Q" if v < 2 else "q"
                else:
                    grid[y][x] = "O" if v < 3 else "o"
    for x in range(cx - 10, cx + 11):
        _put(grid, x, cy + 8, "G")
    return grid


def tile_tree() -> list[list[str]]:
    grid = _grass_base()
    for y in range(19, TILE):
        for x in range(14, 18):
            grid[y][x] = "B" if x >= 16 else "b"
        grid[y][14] = "c"
        grid[y][17] = "B"
    blobs = [(16, 13, 12), (8, 17, 8), (24, 17, 8), (16, 9, 9)]
    for y in range(TILE):
        for x in range(TILE):
            for bx, by, br in blobs:
                if ((x - bx) * 1.05) ** 2 + ((y - by) * 1.0) ** 2 <= br * br:
                    lit = (x < 16 and y < 14) or (x - 16 + y - 13) < -7
                    v = _hash(x >> 1, y >> 1, 81) % 10
                    grid[y][x] = "L" if lit and v < 4 else ("l" if lit else ("d" if v < 4 else "g"))
                    break
    for x in range(5, 28):
        if 26 <= x <= 31 or _hash(x, 0, 82) % 2 == 0:
            _put(grid, x, 30, "G")
    return grid


def tile_stump() -> list[list[str]]:
    """树桩：带年轮的椭圆顶面 + 有木纹的树皮侧壁。"""
    grid = _grass_base()
    cx = 16
    for y in range(15, 26):
        for x in range(cx - 7, cx + 7):
            dx = (x - cx) / 7.0
            dy = (y - 20) / 5.2
            if dx * dx + dy * dy <= 1.0:
                if y <= 18:
                    grid[y][x] = "F"
                else:
                    grid[y][x] = "B" if (x - cx) > 3 else ("b" if (x - cx) < -3 else "c")
                    if _hash(x, y, 91) % 5 == 0:
                        grid[y][x] = "B"
    for r in (2, 4, 6):                                   # 年轮
        for x in range(cx - r, cx + r + 1):
            half = max(0, int(round((3 - r / 2.4) * 0.9)))
            for y in range(15, 15 + max(1, half)):
                if grid[y][x] == "F":
                    grid[y][x] = "c"
    for y in range(15, 19):                                # 顶面受光
        for x in range(cx - 7, cx + 7):
            if grid[y][x] == "F" and (x - cx) + (y - 17) < -3:
                grid[y][x] = "t"
    for x in range(cx - 9, cx + 10):
        if _hash(x, 0, 92) % 3 != 0:
            _put(grid, x, 26, "G")
    return grid


def tile_wheat() -> list[list[str]]:
    """麦田：错行密植 + 顶端麦穗，读起来是田而不是一排栅栏。"""
    grid = tile_path()
    for y in range(TILE):
        for x in range(TILE):
            if _hash(x >> 1, y >> 1, 31) % 14 < 4:
                grid[y][x] = "E"
    for row_y in range(3, TILE, 5):
        offset = 2 if (row_y // 5) % 2 else 0
        for x in range(offset, TILE, 4):
            top = row_y - 2 - (_hash(x, row_y, 32) % 3)
            for y in range(top, row_y + 4):
                grid[y][x] = "Y"
            for dy in range(3):                            # 麦穗
                _put(grid, x, top + dy, "y" if dy % 2 == 0 else "z")
            _put(grid, x - 1, top + 1, "y")
            _put(grid, x + 1, top + 1, "z")
    return grid


def tile_fence() -> list[list[str]]:
    """横栅栏：两根立柱 + 两道横杆，柱子在草地上带一小块投影。"""
    grid = _grass_base()
    for x in range(TILE):
        for y in (12, 13, 20, 21):
            grid[y][x] = "c" if y in (12, 20) else "b"
    for px in (7, 24):
        for y in range(9, 27):
            grid[y][px] = "c"
            grid[y][px + 1] = "b"
            grid[y][px + 2] = "B"
        for x in range(px, px + 3):
            _put(grid, x, 26, "G")
    return grid


def tile_mushroom() -> list[list[str]]:
    """蘑菇：红伞白点 + 奶白柄，轮廓清晰可辨。"""
    grid = _grass_base()
    for mx, my, r in ((11, 20, 4), (23, 25, 3)):
        for dy in range(-r, 1):                            # 伞盖
            span = int(round((r * r - dy * dy) ** 0.5))
            for x in range(mx - span, mx + span + 1):
                grid[my + dy][x] = "k"
        for x in range(mx - 1, mx + 2):                    # 柄
            for y in range(my, my + 4):
                grid[y][x] = "n"
        for dx, dy in ((-1, -r + 1), (1, -r + 1), (0, -r + 2)):   # 白点
            _put(grid, mx + dx, my + dy, "n")
        for dy in range(-r, 0):                            # 伞盖受光
            for x in range(mx - r, mx + r + 1):
                if grid[my + dy][x] == "k" and (x - mx) + dy < -2:
                    grid[my + dy][x] = "h"
        for x in range(mx - r - 1, mx + r + 2):            # 地面投影
            if _hash(x, 0, 101) % 3 != 0:
                _put(grid, x, my + 4, "G")
    return grid


# --------------------------------------------------------------------- 组装

def _tile_specs():
    """21 张瓦片：图集按 7x3 排布。water/water_edge_* 依赖相位，单独处理。"""
    return [
        ("grass", lambda p: tile_grass()),
        ("grass_light", lambda p: tile_grass_light()),
        ("grass_flowers", lambda p: tile_grass_flowers()),
        ("grass_tuft", lambda p: tile_grass_tuft()),
        ("bush", lambda p: tile_bush()),
        ("path", lambda p: tile_path()),
        ("path_edge_n", lambda p: _path_edge("n", 31)),
        ("path_edge_s", lambda p: _path_edge("s", 33)),
        ("path_edge_w", lambda p: _path_edge("w", 35)),
        ("path_edge_e", lambda p: _path_edge("e", 37)),
        ("path_corner_nw", lambda p: _path_corner("nw", 39)),
        ("path_corner_ne", lambda p: _path_corner("ne", 40)),
        ("path_corner_se", lambda p: _path_corner("se", 41)),
        ("path_corner_sw", lambda p: _path_corner("sw", 42)),
        ("water", lambda p: _water(p)),
        ("water_edge_n", lambda p: _water_edge("n", 51, p)),
        ("water_edge_s", lambda p: _water_edge("s", 53, p)),
        ("water_edge_w", lambda p: _water_edge("w", 55, p)),
        ("water_edge_e", lambda p: _water_edge("e", 57, p)),
        ("water_corner_nw", lambda p: _water_corner("nw", 59, p)),
        ("water_corner_ne", lambda p: _water_corner("ne", 60, p)),
        ("water_corner_se", lambda p: _water_corner("se", 61, p)),
        ("water_corner_sw", lambda p: _water_corner("sw", 62, p)),
        ("reeds", lambda p: tile_reeds(p)),
        ("rock", lambda p: tile_rock()),
        ("tree", lambda p: tile_tree()),
        ("stump", lambda p: tile_stump()),
        ("fence", lambda p: tile_fence()),
        ("mushroom", lambda p: tile_mushroom()),
        ("wheat", lambda p: tile_wheat()),
        ("wheat_edge_w", lambda p: _edge_tile(tile_wheat(), _grass_base(), "w", 71)),
        ("wheat_edge_e", lambda p: _edge_tile(tile_wheat(), _grass_base(), "e", 72)),
    ]


TILE_NAMES = [name for name, _ in _tile_specs()]
# 含水的瓦片都随帧变化（芦苇画在水上，所以也算），别手写这张表
ANIMATED = {"reeds"} | {name for name in TILE_NAMES if name.startswith("water")}


def tile_matrix(name: str, phase: int = 0) -> list[list[str]]:
    for tile_name, builder in _tile_specs():
        if tile_name == name:
            return builder(phase)
    raise KeyError(name)


def sheet_frame(phase: int) -> list[list[str]]:
    grid = blank(SHEET_COLS * TILE, SHEET_ROWS * TILE)
    for idx, (name, builder) in enumerate(_tile_specs()):
        src = builder(phase)
        ox = (idx % SHEET_COLS) * TILE
        oy = (idx // SHEET_COLS) * TILE
        for y in range(TILE):
            for x in range(TILE):
                grid[oy + y][ox + x] = src[y][x]
    return grid


# 12x8 示例场景：树线 -> 草地 -> 小径 + 池塘 + 麦田 + 栅栏
#   .  空白
SCENE_MAP: list[list[str]] = [
    ["tree", "tree", "grass", "grass_light", "bush", "grass", "grass_flowers", "grass_tuft", "grass", "rock", "grass", "tree"],
    ["grass", "grass_tuft", "grass", "grass_flowers", "grass", "grass_light", "grass", "grass", "grass_tuft", "grass", "grass", "grass"],
    ["bush", "grass", "grass", "path_edge_n", "path_edge_n", "grass", "grass", "water_corner_nw", "water_edge_n", "water_edge_n", "reeds", "grass"],
    ["grass", "grass", "path_edge_w", "path", "path", "grass", "grass", "water_edge_w", "water", "water", "water", "water"],
    ["grass", "grass", "path_edge_w", "path", "path", "path", "path_edge_e", "grass", "water_edge_w", "water", "rock", "water"],
    ["grass", "grass_flowers", "path_edge_w", "path", "path", "path", "path_edge_e", "grass", "water_edge_w", "water", "water", "water"],
    ["grass_flowers", "grass", "path_edge_s", "path_edge_s", "path_edge_s", "grass", "wheat_edge_w", "wheat", "wheat_edge_e", "grass", "grass", "stump"],
    ["grass", "mushroom", "grass", "grass_tuft", "fence", "grass", "wheat_edge_w", "wheat", "wheat_edge_e", "mushroom", "rock", "grass"],
]


def scene() -> list[list[str]]:
    """把瓦片拼成场景。带动画的瓦片按位置错开相位，否则一片水面就是同一张贴图盖 20 次。"""
    grid = blank(SCENE_COLS * TILE, SCENE_ROWS * TILE)
    for ty, row in enumerate(SCENE_MAP):
        for tx, name in enumerate(row):
            if name == ".":
                continue
            src = tile_matrix(name, (tx + ty) % WATER_PHASES if name in ANIMATED else 0)
            ox, oy = tx * TILE, ty * TILE
            for y in range(TILE):
                for x in range(TILE):
                    grid[oy + y][ox + x] = src[y][x]
    return grid


# --------------------------------------------------------------------- 网格文件

def grid_lua(matrix: list[list[str]], title: str) -> str:
    """paint_grid 用的 Lua 数据文件（该版本 json.decode 返回 userdata，只能 dofile）。"""
    used = {code for row in matrix for code in row if code != "."}
    palette = ", ".join(f'{code} = "{PAL[code]}"' for code in sorted(used))
    rows = ",\n  ".join('"%s"' % "".join(row) for row in matrix)
    return f"-- {title}\nreturn {{\n  palette = {{ {palette} }},\n  rows = {{\n  {rows},\n  }},\n}}\n"