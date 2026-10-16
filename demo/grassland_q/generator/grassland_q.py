"""Q版草原 tileset 的像素美术定义（纯 Python，确定性生成）。

和上一版"写实草原"的区别在美术规则，不在工具：
- **圆优先**：所有实体（树冠、灌木、石块、麦穗、芦苇、蘑菇）都是圆角团块，
  Q版的可爱感来自轮廓的圆钝，而不是加描边；
- **两级明度 + 一个高光**：每种材质只有 base / shade / light 三档，亮部一律在左上，
  不用高频抖动堆细节 —— 高频噪点是"写实"的敌人，也是 Q版显得脏的元凶；
- **大色块 + 少量点缀**：一朵花就是一个可辨认的形状，5px 花瓣加 1px 花心就够了；
- **每张瓦片都要有一个焦点**：Q版素材缩到很小也得一眼看出画的是什么。

对外暴露：TILE_NAMES / tile_matrix(name, phase) / sheet_frame(phase) / scene() / grid_lua()。
produce.py 负责把它们送进 Aseprite 并逐像素校验。
"""

from __future__ import annotations

TILE = 32
SHEET_COLS = 8
SHEET_ROWS = 4
SCENE_COLS = 12
SCENE_ROWS = 8
WATER_PHASES = 4

# 调色板：每个材质三档（base / shade / light）+ 少量高光与点缀色
PAL: dict[str, str] = {
    # 草：明亮偏黄的嫩绿
    "g": "#7CC152",   # base
    "G": "#63A845",   # shade
    "l": "#96D46F",   # light
    "L": "#B8E58F",   # 高光
    "d": "#47893A",   # 深部（树冠暗面 / 根部）
    # 泥土路：暖沙色，比上一版更亮更甜
    "e": "#D8A46A",
    "E": "#C08A52",
    "f": "#E8BC8C",
    "F": "#F5DDB4",
    # 水：偏亮的湖蓝
    "w": "#5FC0E8",
    "W": "#3E9BD0",
    "r": "#8AD8F5",
    "R": "#C8F0FF",
    # 沙滩
    "s": "#F2DCA8",
    "S": "#E4C78C",
    "t": "#FBEBC8",
    # 石：偏冷偏粉的灰
    "o": "#B8BCC8",
    "O": "#9096A4",
    "q": "#D8DCE6",
    # 木：暖棕
    "b": "#B07A4A",
    "B": "#8A5A32",
    "c": "#D09A66",
    # 麦：金黄
    "y": "#F5D06A",
    "Y": "#D9A93E",
    "z": "#FFE9A8",
    # 点缀
    "p": "#FF9DB0",   # 粉花
    "h": "#FFD166",   # 黄花
    "m": "#B58BE8",   # 紫花
    "k": "#FF7A6B",   # 蘑菇伞
    "n": "#FFE8D6",   # 蘑菇柄
    "u": "#FFF3B0",   # 奶油花心 / 浪花
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


def _disc(grid, cx, cy, rx, ry, color, squash=1.0):
    """圆角椭圆。squash < 1 压扁（做蘑菇伞、影子）。"""
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            dx = (x - cx) / max(rx, 0.5)
            dy = (y - cy) / max(ry, 0.5) * squash
            if dx * dx + dy * dy <= 1.0:
                _put(grid, x, y, color)


def _ring(grid, cx, cy, rx, ry, color, squash=1.0):
    """椭圆描边（给团块勾一圈暗边，Q版靠它"立"起来）。"""
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            dx = (x - cx) / max(rx, 0.5)
            dy = (y - cy) / max(ry, 0.5) * squash
            d = dx * dx + dy * dy
            if 0.72 <= d <= 1.0:
                _put(grid, x, y, color)


def _wave(grid, x0, x1, y, color, amp=2, period=12):
    """一段起伏的水波线（Q版水面靠它读出"流动"）。"""
    for x in range(x0, x1):
        t = (x - x0) % period
        dy = -amp if (t < period // 4 or period // 2 <= t < 3 * period // 4) else 0
        _put(grid, x, y + dy, color)


# --------------------------------------------------------------------- 草

def _grass_base(light: bool = False) -> list[list[str]]:
    """草地：大色块 + 极少量噪点，每 2x2 一档，避免变成雪花。"""
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            v = _hash(x >> 1, y >> 1, 1) % 10
            if light:
                grid[y][x] = "l" if v < 6 else "g"
            else:
                grid[y][x] = "G" if v < 3 else "g"
    for y in range(TILE):                       # 一点点高光碎点，稀疏到几乎看不见
        for x in range(TILE):
            if _hash(x, y, 7) % 53 == 0:
                _put(grid, x, y, "L")
    return grid


def _sprig(grid, cx, by, h=7, lean=1):
    """一丛三叶小草：根部压深、叶片带高光，否则会和草地底色糊成一片。"""
    for dx in range(-2, 3):
        _put(grid, cx + dx, by, "d")
    for dx, hgt in ((-lean, h - 2), (0, h), (lean, h - 1)):
        for dy in range(hgt):
            _put(grid, cx + dx, by - dy, "L" if dy > hgt * 0.45 else "G")
        _put(grid, cx + dx, by - hgt + 1, "l")
    _put(grid, cx - lean, by - (h - 2) + 1, "g")
    _put(grid, cx + lean, by - (h - 1) + 1, "g")
    _put(grid, cx, by - h, "L")


def _clover(grid, cx, cy):
    """三叶草点缀：三个小圆点 + 一根短茎。"""
    _put(grid, cx, cy + 1, "d")
    _put(grid, cx, cy + 2, "d")
    for dx, dy in ((-1, -1), (1, -1), (0, -2)):
        _put(grid, cx + dx, cy + dy, "L")
    _put(grid, cx, cy - 1, "l")


def tile_grass() -> list[list[str]]:
    grid = _grass_base()
    _sprig(grid, 9, 27, 8)
    _sprig(grid, 23, 24, 6)
    _clover(grid, 18, 15)
    return grid


def tile_grass_light() -> list[list[str]]:
    """阳光照到的一小块：整体提亮一档，用来打散大面积铺开的重复感。"""
    grid = _grass_base(light=True)
    _sprig(grid, 14, 26, 7)
    _clover(grid, 24, 14)
    return grid


def tile_grass_tuft() -> list[list[str]]:
    """高草：中间那丛要够宽够高才读得出来，所以给中叶加宽、给草丛加一块软影。"""
    grid = _grass_base()
    for cx, by in ((11, 30), (24, 28)):
        _disc(grid, cx, by, 7, 2.6, "G")              # 软影压住草丛
        for dx in range(-2, 3):
            _put(grid, cx + dx, by, "d")
    for dy in range(12):                               # 中叶加宽成 2px
        _put(grid, 11, 30 - dy, "G")
        _put(grid, 12, 30 - dy, "L" if dy > 5 else "G")
    _put(grid, 11, 18, "L")
    _put(grid, 12, 18, "L")
    _sprig(grid, 6, 27, 8)
    _sprig(grid, 19, 26, 7)
    _sprig(grid, 26, 30, 6)
    return grid


def _flower(grid, cx, cy, petal, heart="u", stem=5):
    """一朵圆花：直径 5 的花瓣盘 + 花心 + 短茎，缩到很小也认得出。"""
    for y in range(-2, 3):
        for x in range(-2, 3):
            if x * x + y * y <= 5:
                _put(grid, cx + x, cy + y, petal)
    _put(grid, cx, cy, heart)
    _put(grid, cx - 1, cy - 1, heart) if petal != heart else None
    for dy in range(stem):
        _put(grid, cx, cy + 3 + dy, "d")
    _put(grid, cx + 1, cy + 4, "G")


def tile_grass_flowers() -> list[list[str]]:
    grid = _grass_base()
    _flower(grid, 8, 18, "p", "u")
    _flower(grid, 22, 23, "h", "u")
    _flower(grid, 15, 12, "m", "u", stem=4)
    _clover(grid, 26, 9)
    return grid


def tile_bush() -> list[list[str]]:
    """圆灌木：三团叠加 + 暗边 + 脚下软影。"""
    grid = _grass_base()
    for cx, cy, r in ((16, 19, 10), (9, 23, 7), (23, 23, 7)):
        _disc(grid, cx, cy, r, r * 0.86, "g")
        _ring(grid, cx, cy, r, r * 0.86, "d")
    for cx, cy, r in ((13, 16, 3.5), (19, 15, 2.6), (10, 20, 2.2)):   # 小颗高光，别糊成一片
        _disc(grid, cx, cy, r, r * 0.8, "l")
    for dx in range(-9, 10):                                            # 脚下软影：中间浓两头淡
        _put(grid, 16 + dx, 30, "G" if abs(dx) < 7 else "g")
    return grid


# --------------------------------------------------------------------- 路径

def tile_path() -> list[list[str]]:
    """暖沙色小路：两个大色阶 + 几颗圆石子。"""
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            v = _hash(x >> 1, y >> 1, 11) % 10
            grid[y][x] = "E" if v < 3 else "e"
    for x, y in ((7, 9), (22, 6), (13, 20), (26, 24), (5, 26)):
        _disc(grid, x, y, 2, 1.6, "f")
        _put(grid, x, y - 1, "F")
    for x, y in ((17, 13), (9, 17)):                      # 偶尔一块深色小石
        _disc(grid, x, y, 1.6, 1.4, "E")
        _put(grid, x, y, "B" if False else "b")
    return grid


def _edge_tile(base, neighbor, side, salt, inset=12) -> list[list[str]]:
    """在 base 上切一条柔和边界并把 neighbor 渐入；`side` 指邻居所在的那条边。

    过渡用 2 格棋盘抖动，Q版要"软"，硬切会像贴纸。
    """
    grid = [row[:] for row in base]

    def pos(i: int) -> int:
        return inset + _hash(i, 0, salt) % 3

    for i in range(TILE):
        for t in range(5):
            if side == "n":
                y, x = pos(i) - t, i
            elif side == "s":
                y, x = TILE - 1 - pos(i) + t, i
            elif side == "w":
                y, x = i, pos(i) - t
            else:
                y, x = i, TILE - 1 - pos(i) + t
            if not (0 <= y < TILE and 0 <= x < TILE):
                continue
            if t < 2:
                grid[y][x] = neighbor[y][x]
            elif t < 4:
                grid[y][x] = neighbor[y][x] if (i + t) % 2 == 0 else base[y][x]
            else:
                grid[y][x] = neighbor[y][x] if (i + t) % 3 == 0 else base[y][x]
    return grid


def _path_edge(side: str, salt: int) -> list[list[str]]:
    grid = _edge_tile(tile_path(), _grass_base(), side, salt)
    for i in range(TILE):                                  # 草叶探头压在路上
        if _hash(i, 0, salt + 1) % 4:
            continue
        p = 12 + _hash(i, 0, salt) % 3
        if side == "n":
            _put(grid, i, p - 1, "l")
            _put(grid, i, p, "L")
        elif side == "s":
            _put(grid, i, TILE - p, "l")
            _put(grid, i, TILE - p - 1, "L")
        elif side == "w":
            _put(grid, p - 1, i, "l")
            _put(grid, p, i, "L")
        else:
            _put(grid, TILE - p, i, "l")
            _put(grid, TILE - p - 1, i, "L")
    return grid


def _path_corner(corner: str, salt: int) -> list[list[str]]:
    """路径转角：象限圆弧，路面在象限内侧。"""
    path, grass = tile_path(), _grass_base()
    grid = blank()
    flip_x = corner in ("ne", "se")
    flip_y = corner in ("sw", "se")
    off = TILE - 14
    for y in range(TILE):
        for x in range(TILE):
            dx = (TILE - 1 - x if flip_x else x) - off
            dy = (TILE - 1 - y if flip_y else y) - off
            dist = (dx * dx + dy * dy) ** 0.5
            r = 16 + _hash(x, y, salt) % 3
            grid[y][x] = path[y][x] if dist < r else grass[y][x]
            if r - 1 <= dist < r + 1:
                grid[y][x] = path[y][x] if (x + y) % 2 == 0 else grass[y][x]
    return grid


# --------------------------------------------------------------------- 水与沙岸

def _sand_base() -> list[list[str]]:
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            v = _hash(x >> 1, y >> 1, 51) % 10
            grid[y][x] = "S" if v < 3 else "s"
    for x, y in ((9, 18), (24, 24)):                      # 圆圆的贝壳小石（少一点，岸边才干净）
        _disc(grid, x, y, 2, 1.6, "t")
        _put(grid, x, y - 1, "t")
    return grid


def _water(phase: int) -> list[list[str]]:
    """Q版水面：两三段起伏的波线 + 一两个浪尖高光。

    水体本身是**均匀**的一档蓝：每张瓦片都画一条"底部渐深"的渐变，铺成池塘后
    每 32px 就重复一次，整片水域会出现横向条带。渐变属于地形，不属于水。
    """
    grid = blank()
    for y in range(TILE):
        for x in range(TILE):
            grid[y][x] = "w"
    for row, salt in ((8, 1), (17, 2), (25, 3)):
        y = (row + phase * 2) % TILE
        if _hash(row, 0, salt) % 3:
            continue
        _wave(grid, 2, TILE - 1, y, "r", amp=2, period=14)
        _wave(grid, 6, TILE - 5, y + 2, "r", amp=1, period=11)
    for x, row in ((7, 13), (23, 21), (15, 29)):          # 圆润的浪尖高光
        yy = (row + phase * 2) % TILE
        if _hash(x, row, 9) % 3:
            _disc(grid, x, yy, 2, 1.4, "R")
    return grid


def _foam(grid, x, y, r=2):
    """一团圆浪花。"""
    _disc(grid, x, y, r, r * 0.8, "R")
    _put(grid, x - 1, y - 1, "u")


def _water_edge(side: str, salt: int, phase: int) -> list[list[str]]:
    """水域过渡砖：实心沙带 -> 两色抖动 -> 边界一串圆浪花。"""
    sand, water = _sand_base(), _water(phase)
    grid = _edge_tile(water, sand, side, salt, inset=11)
    for i in range(TILE):
        p = 11 + _hash(i, 0, salt) % 3
        if side == "n":
            y, x = p, i
        elif side == "s":
            y, x = TILE - 1 - p, i
        elif side == "w":
            y, x = i, p
        else:
            y, x = i, TILE - 1 - p
        if _hash(i, 0, salt + 2) % 3:
            _foam(grid, x, y, 2 if _hash(i, 1, salt) % 2 else 1)
    return grid


def _water_corner(corner: str, salt: int, phase: int) -> list[list[str]]:
    """水域转角：象限圆弧 + 弧边上的圆浪花。"""
    sand, water = _sand_base(), _water(phase)
    grid = blank()
    flip_x = corner in ("ne", "se")
    flip_y = corner in ("sw", "se")
    off = TILE - 14
    for y in range(TILE):
        for x in range(TILE):
            dx = (TILE - 1 - x if flip_x else x) - off
            dy = (TILE - 1 - y if flip_y else y) - off
            dist = (dx * dx + dy * dy) ** 0.5
            r = 17 + _hash(x, y, salt) % 3
            grid[y][x] = water[y][x] if dist < r else sand[y][x]
            if r - 1 <= dist < r + 1:
                grid[y][x] = water[y][x] if (x + y) % 2 == 0 else sand[y][x]
            elif r <= dist < r + 3 and _hash(x, y, salt + 1) % 2 == 0:
                grid[y][x] = "t"
            elif abs(dist - r) < 1.6 and _hash(x, y, salt + 2) % 5 == 0:
                grid[y][x] = "R"
    return grid


def tile_reeds(phase: int = 1) -> list[list[str]]:
    """Q版香蒲：圆头蒲棒 + 两片细叶，成丛。"""
    grid = _water(phase)
    for cx, by in ((8, 30), (15, 31), (23, 29), (28, 30)):
        top = by - 15 - (_hash(cx, 0, 61) % 4)
        for y in range(top + 5, by):
            _put(grid, cx, y, "G")
        _disc(grid, cx, top + 2, 2, 3, "b")                # 蒲棒
        _disc(grid, cx, top + 1, 2, 3, "c")
        _put(grid, cx - 1, top, "c")
        _put(grid, cx + 1, top + 3, "B")
        _put(grid, cx - 2, by - 4, "l")                    # 侧叶
        _put(grid, cx - 2, by - 3, "G")
        _put(grid, cx + 2, by - 5, "l")
        _put(grid, cx + 2, by - 4, "G")
    return grid


# --------------------------------------------------------------------- 物件

def tile_rock() -> list[list[str]]:
    """圆石：一大两小，带高光和软影。"""
    grid = _grass_base()
    _disc(grid, 15, 20, 11, 8, "o")
    _ring(grid, 15, 20, 11, 8, "O")
    _disc(grid, 11, 17, 5, 3.4, "q")
    _disc(grid, 20, 22, 3, 2.2, "q")
    _disc(grid, 26, 26, 4, 3, "o")
    _ring(grid, 26, 26, 4, 3, "O")
    _disc(grid, 25, 25, 2, 1.4, "q")
    _disc(grid, 15, 29, 12, 2.6, "G")
    return grid


def tile_tree() -> list[list[str]]:
    """棒棒糖树：圆润树冠 + 暖棕树干 + 脚下软影。"""
    grid = _grass_base()
    for y in range(16, TILE):                              # 树干（比上一版更高更粗）
        _put(grid, 14, y, "c")
        _put(grid, 15, y, "c")
        _put(grid, 16, y, "b")
        _put(grid, 17, y, "B")
    for dx in range(-2, 3):
        _put(grid, 16 + dx, 31, "d")
    for cx, cy, r in ((16, 12, 12), (8, 15, 8), (24, 15, 8), (16, 6, 8)):
        _disc(grid, cx, cy, r, r * 0.92, "g")
        _ring(grid, cx, cy, r, r * 0.92, "d")
    for cx, cy, r in ((13, 10, 5), (20, 8, 3), (10, 13, 2.4)):   # 高光团
        _disc(grid, cx, cy, r, r * 0.8, "l")
    _put(grid, 11, 10, "L")
    _put(grid, 20, 12, "L")
    return grid


def tile_stump() -> list[list[str]]:
    """树桩：圆截面 + 同心年轮 + 一圈树皮。"""
    grid = _grass_base()
    cx = 16
    for y in range(14, 28):
        for x in range(cx - 8, cx + 9):
            dx = (x - cx) / 8.0
            dy = (y - 21) / 6.6
            if dx * dx + dy * dy <= 1.0:
                grid[y][x] = "b" if (x - cx) < -3 else ("B" if (x - cx) > 3 else "c")
    for y in range(14, 19):                                # 顶面
        for x in range(cx - 8, cx + 9):
            dx = (x - cx) / 8.0
            dy = (y - 17) / 3.4
            if dx * dx + dy * dy <= 1.0:
                grid[y][x] = "F"
    for r, dy in ((5, 16.6), (3, 16.9), (1.4, 17.1)):     # 年轮
        for x in range(cx - 7, cx + 8):
            if grid[16][x] == "F" and abs(x - cx) <= r:
                grid[16][x] = "c"
    for x in range(cx - 7, cx - 3):                       # 顶面受光
        if grid[15][x] == "F":
            grid[15][x] = "t"
    _disc(grid, cx, 29, 10, 2.4, "G")
    return grid


def tile_fence() -> list[list[str]]:
    """圆头栅栏：两根立柱 + 两道横杆，柱头切个圆角。"""
    grid = _grass_base()
    for x in range(TILE):
        for y in (12, 13, 20, 21):
            grid[y][x] = "c" if y in (12, 20) else "b"
    for px in (7, 24):
        for y in range(10, 27):
            grid[y][px] = "c"
            grid[y][px + 1] = "b"
            grid[y][px + 2] = "B"
        grid[9][px] = grid[9][px + 1] = "c"                # 圆柱头
        grid[10][px] = "c"
        _disc(grid, px + 1, 28, 4, 1.6, "G")
    return grid


def tile_mushroom() -> list[list[str]]:
    """Q版蘑菇：圆伞 + 奶白点 + 胖胖的柄。"""
    grid = _grass_base()
    for mx, my, r in ((12, 19, 5), (24, 24, 4)):
        for y in range(my - r, my + 1):
            span = int(round((r * r - (my - y - r) ** 2) ** 0.5)) if (my - y - r) ** 2 <= r * r else 0
            for x in range(mx - span, mx + span + 1):
                grid[y][x] = "k"
        _disc(grid, mx - 1, my - r + 2, 2, 1.4, "F")      # 伞盖高光
        for dx, dy in ((-1, -r + 2), (1, -r + 2), (0, -r + 3)):
            _put(grid, mx + dx, my + dy, "n")
        for y in range(my, my + 4):                        # 柄
            _put(grid, mx - 1, y, "n")
            _put(grid, mx, y, "u")
        _put(grid, mx + 1, my + 3, "S")
        _disc(grid, mx, my + 4, r, 1.6, "G")
    return grid


def tile_wheat() -> list[list[str]]:
    """麦田：错行胖麦穗，每穗一个焦点。"""
    grid = tile_path()
    for y in range(TILE):
        for x in range(TILE):
            if _hash(x >> 1, y >> 1, 31) % 12 < 3:
                grid[y][x] = "E"
    for row_y in range(4, TILE, 6):
        offset = 3 if (row_y // 6) % 2 else 0
        for x in range(offset, TILE, 5):
            top = row_y - 3 - (_hash(x, row_y, 32) % 3)
            _put(grid, x, top + 3, "Y")
            _put(grid, x, top + 4, "Y")
            _put(grid, x, top + 5, "y")
            _disc(grid, x, top + 1, 2, 3, "y")            # 圆头麦穗
            _put(grid, x, top, "z")
            _put(grid, x - 1, top + 2, "z")
            _put(grid, x + 1, top + 2, "y")
            _put(grid, x - 1, top + 4, "Y")
            _put(grid, x + 1, top + 4, "Y")
    return grid


def _wheat_edge(side: str, salt: int) -> list[list[str]]:
    grid = _edge_tile(tile_wheat(), _grass_base(), side, salt)
    for i in range(TILE):
        if _hash(i, 0, salt + 1) % 5:
            continue
        p = 12 + _hash(i, 0, salt) % 3
        if side == "w":
            _put(grid, p - 1, i, "l")
            _put(grid, p, i, "L")
        else:
            _put(grid, TILE - p, i, "l")
            _put(grid, TILE - p - 1, i, "L")
    return grid


# --------------------------------------------------------------------- 组装

def _tile_specs():
    """32 张瓦片，正好填满 8x4 图集。water* 与 reeds 随相位变化。"""
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
        ("wheat_edge_w", lambda p: _wheat_edge("w", 71)),
        ("wheat_edge_e", lambda p: _wheat_edge("e", 72)),
    ]


TILE_NAMES = [name for name, _ in _tile_specs()]
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
        ox, oy = (idx % SHEET_COLS) * TILE, (idx // SHEET_COLS) * TILE
        for y in range(TILE):
            for x in range(TILE):
                grid[oy + y][ox + x] = src[y][x]
    return grid


# 12x8 场景：树线 -> 草地 + 十字小径 -> 圆角池塘 + 麦田 + 栅栏
# 路的宽度控制在 2 格：铺到 3-4 格宽就不再像路，而像一块空地。
SCENE_MAP: list[list[str]] = [
    ["tree", "tree", "grass", "grass_light", "bush", "grass", "grass_flowers", "grass_tuft", "grass", "rock", "grass", "tree"],
    ["grass", "grass_tuft", "grass", "grass_flowers", "grass", "grass_light", "grass", "grass", "grass_tuft", "grass", "grass", "grass"],
    ["bush", "grass", "grass", "path_edge_n", "path_edge_n", "grass", "grass", "grass", "water_corner_nw", "water_edge_n", "water_edge_n", "water"],
    ["grass", "grass", "path_edge_w", "path", "path", "path", "path_edge_e", "grass", "water_edge_w", "water", "water", "reeds"],
    ["grass", "grass", "path_edge_w", "path", "path", "grass", "grass_light", "grass", "water_edge_w", "water", "rock", "water"],
    ["grass", "grass_flowers", "path_edge_w", "path", "path", "grass", "grass", "grass", "water_edge_w", "water", "water", "water"],
    ["grass_flowers", "grass", "path_edge_s", "path_edge_s", "grass", "wheat_edge_w", "wheat", "wheat_edge_e", "water_corner_sw", "water_edge_s", "water_edge_s", "water_edge_s"],
    ["grass", "mushroom", "grass", "grass_tuft", "fence", "grass", "wheat_edge_w", "wheat", "wheat_edge_e", "grass", "mushroom", "rock"],
]


def scene() -> list[list[str]]:
    """把瓦片拼成场景。带动画的瓦片按位置错开相位，否则一片水面就是同一张贴图盖 N 次。"""
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


def grid_lua(matrix: list[list[str]], title: str) -> str:
    """paint_grid 用的 Lua 数据文件（该版本 json.decode 返回 userdata，只能 dofile）。"""
    used = {code for row in matrix for code in row if code != "."}
    palette = ", ".join(f'{code} = "{PAL[code]}"' for code in sorted(used))
    rows = ",\n  ".join('"%s"' % "".join(row) for row in matrix)
    return f"-- {title}\nreturn {{\n  palette = {{ {palette} }},\n  rows = {{\n  {rows},\n  }},\n}}\n"