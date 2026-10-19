"""荒野 tileset 的设计模型：调色板、材质、47-blob 几何、边界着色、图集与场景。

不碰 Aseprite —— 这里只产出字符矩阵（每个字符是 PAL 的一个色键，'.' 是透明）。
produce.py 把矩阵交给 paint_grid 落进 Aseprite，再逐像素比对回来。

## 47-blob 的构造（这套图集的地基）

一个瓦片有 4 条边（N/E/S/W）和 4 个角（NE/SE/SW/NW）共 8 个邻居位。角位只有在
**相邻两条边都置位**时才有视觉意义，否则它和"该角未置位"画出来完全相同 —— 于是
16 种边组合各自允许的角子集加起来正好 47 种：

    0 边 1 + 1 边 4 + 相邻 2 边 8 + 相对 2 边 2 + 3 边 16 + 4 边 16 = 47

几何规则（`MARGIN` = 内缩像素，瓦片边长 `TILE`）：

- 中心方块 [M, T-M]² 永远被叠加地形覆盖；
- 每条置位的边把覆盖推到那一侧的瓦片边界；
- 四个角方格各自四选一：
  **相邻两边都置位且角位也置位** -> 填满（直角衔接）；
  **相邻两边都置位但角位未置位** -> 以角内点为圆心、半径 M 的四分之一圆盘
  （两条带子之间用内凹弧顺过去）；
  **只有一条邻边置位** -> 填满（角方格是那条带子的一部分，边界因此在瓦片边缘收成
  直线，而不是每格鼓一个包）；
  **两条邻边都没置位** -> 留给基底，并把中心方块在这个角上的直角**向内**削成半径 M
  的圆角（带子端头读成半圆）。

"只有一条邻边"这一支曾经画成向内削圆，于是一条直边的两端各鼓一个半圆、一排瓦片连
起来读成齿轮 / 云朵 —— `selfcheck()` 的接缝契约就是为钉住这类错误而写的。
`blob_configs()` 枚举这 47 个位掩码，`mask_for()` 栅格化。

## 位掩码约定（manifest.json 里就是这个数）

    bit0=N  bit1=E  bit2=S  bit3=W  bit4=NE  bit5=SE  bit6=SW  bit7=NW

图集按掩码升序排列，槽位号 = 行主序下标；导入引擎时以 manifest 为准，不要按肉眼
顺序猜。
"""

import json
from pathlib import Path

TILE = 32
# 内缩量就是转角的圆弧半径：8（四分之一格）在 32px 上会把直边读成一串半圆，
# 整片地形像云朵；6 只留下"这块地形圆了个角"的感觉。
MARGIN = 6
WATER_PHASES = 4
COLS = 12

# ---------------------------------------------------------------- 调色板

PAL = {
    # 草地（光源左上）
    'g': "#8CCF63",   # 亮
    'G': "#63B044",   # 中
    'h': "#478C35",   # 暗
    'H': "#2F6B26",   # 最深（投影）
    # 泥土路
    'd': "#C7975E",
    'D': "#A57441",
    'k': "#7E5530",
    'K': "#5A3B21",
    # 沙
    's': "#F2E0A8",
    'S': "#DDC384",
    'n': "#BEA267",
    'N': "#9A8050",
    # 水
    'w': "#8FE0F2",   # 浪花/高光
    'W': "#4FA9D8",   # 中
    'v': "#2E7CB4",   # 深
    'V': "#1B568A",   # 最深
    # 岩石
    'r': "#CBD1DA",
    'R': "#98A0AE",
    't': "#6C7484",
    'T': "#474D5C",
    # 硬物件描边
    'o': "#241F2B",
    # 物件
    'e': "#3B7A2E",   # 深绿（树冠暗部/芦苇）
    'u': "#7B4A24",   # 树干
    'U': "#54301A",   # 树干暗
    'f': "#FFE14D",   # 黄花
    'F': "#FF7A96",   # 粉花
    'b': "#7FC4F0",   # 蓝花
    'm': "#D2494B",   # 蘑菇伞
    'M': "#F2E6CF",   # 蘑菇柄
    'p': "#4F9E3F",   # 睡莲叶
}

# ---------------------------------------------------------------- 噪声

_MASK32 = 0xFFFFFFFF


def _h(x, y, seed):
    v = (x * 374761393 + y * 668265263 + seed * 1442695041) & _MASK32
    v = ((v ^ (v >> 13)) * 1274126177) & _MASK32
    return (v ^ (v >> 16)) & _MASK32


def _u01(x, y, seed):
    return _h(x, y, seed) / _MASK32


def _vnoise(x, y, cell, seed):
    """块状值噪声：格点索引按瓦片取模，所以平铺必然无缝。"""
    w = TILE // cell
    return _u01((x // cell) % w, (y // cell) % w, seed)


# ---------------------------------------------------------------- 材质
#
# 像素材质的规矩：**大面积平色 + 稀疏结构化细节**。块状值噪声按格点铺满整张图会读成
# 波点（第一版踩过），所以这里低频场只用来压出几块大色斑，细节一律是 2-3 像素的
# 可辨认笔触（草叶、砾石、波纹），并且画在取模的格点上 —— 平铺必然无缝。

def mat_grass(x, y, seed=0):
    v = _vnoise(x, y, 16, seed)
    c = 'g' if v > 0.82 else ('h' if v < 0.08 else 'G')
    if _h(x // 8, y // 8, seed + 3) % 6 == 0:           # 一撮草叶：亮两格、根上一格暗
        lx, ly = x % 8, y % 8
        if (lx, ly) in ((3, 3), (3, 4)):
            c = 'g'
        elif (lx, ly) == (4, 5):
            c = 'h'
    return c


def mat_dirt(x, y, seed=0):
    c = 'D'
    if _vnoise(x, y, 16, seed + 101) < 0.14:            # 踩实了的暗色车辙
        c = 'k'
    if _h(x // 8, y // 8, seed + 211) % 5 == 0:         # 砂砾：两格亮 + 左下一格暗
        lx, ly = x % 8, y % 8
        if (lx, ly) in ((2, 2), (3, 2)):
            c = 'd'
        elif (lx, ly) == (2, 3):
            c = 'K'
    return c


def mat_sand(x, y, seed=0):
    c = 'S'
    if _vnoise(x, y, 16, seed + 307) < 0.12:
        c = 'n'
    band, lane = y % 8, (y // 8) % 2                    # 风成波纹：半数条带里、半段长
    if band == 3 + 4 * lane and _h((x // 16 + lane) % 2, y // 8, seed + 713) % 2:
        if (x + 8 * lane) % 16 < 6:
            c = 's'
    return c


def mat_water(x, y, phase=0, depth=0, seed=0):
    """水深只能按"离岸距离"分档，而且**远档必须和 interior 砖完全相同** ——
    否则在岸砖与 interior 砖的交界处会横出一条与地形无关的硬线。
    所以这里只有"岸边两格浅水"和"其余一律中档"两级，深色只用作波峰下的暗线。
    """
    c = 'w' if depth == 2 else 'W'
    band = y % 8
    if band in (3, 4) and depth > 3 and _h(x // 16, y // 8, seed + 911) % 3 == 0:
        # 波峰亮线 + 线下一格暗线，成对才读得出浪；横向周期 16、随相位平移
        if (x + phase * 4) % 16 < 4:
            c = 'w' if band == 3 else 'v'
    return c


def mat_rock(x, y, seed=0):
    c = 'R'
    v = _vnoise(x, y, 16, seed + 503)
    if v > 0.80:
        c = 'r'
    elif v < 0.14:
        c = 't'
    if _h(x // 8, y // 8, seed + 601) % 13 == 0 and x % 8 == 4 and y % 8 > 3:
        c = 'T'                                         # 裂纹：稀疏、单格、别排成网格
    return c


# ---------------------------------------------------------------- blob 几何

N, E, S, W, NE, SE, SW, NW = 1, 2, 4, 8, 16, 32, 64, 128
CORNER_EDGES = {NE: (N, E), SE: (S, E), SW: (S, W), NW: (N, W)}
CORNER_INNER = {NE: (TILE - MARGIN, MARGIN), SE: (TILE - MARGIN, TILE - MARGIN),
                SW: (MARGIN, TILE - MARGIN), NW: (MARGIN, MARGIN)}
# 角位未置位时要挖的那个"外角点"：瓦片的真角，不是角内点
CORNER_OUTER = {NE: (TILE, 0), SE: (TILE, TILE), SW: (0, TILE), NW: (0, 0)}


def blob_configs():
    """47 个位掩码，升序。角位只在相邻两边都置位时才存在。"""
    out = []
    for edges in range(16):
        # 角位只有在相邻两条边都置位时才有意义，否则画出来和"该角未置位"完全相同
        free = [bit for bit, (a, b) in CORNER_EDGES.items()
                if (edges & a) and (edges & b)]
        for pick in range(1 << len(free)):
            m = edges
            for i, bit in enumerate(free):
                if pick & (1 << i):
                    m |= bit
            out.append(m)
    assert len(out) == 47, len(out)
    return sorted(out)


CONFIGS = blob_configs()


def mask_for(bits):
    """位掩码 -> 32x32 叠加区布尔栅格（像素中心落在区域内即覆盖）。

    模型是**减法**：从"整格都是叠加地形"出发，每条**未**置位的边沿边挖掉宽 MARGIN 的
    **通长**基底带，然后逐角收拾：

    - 相邻两边都置位、角位也置位 -> 不动，角方格留在叠加区里（直角衔接）；
    - 相邻两边都置位、角位未置位 -> 以瓦片的**外角点**为圆心挖掉半径 MARGIN 的四分之一
      圆盘：基底从角上圆滑地凸进来，这就是 blob 的"内角"砖；
    - 恰好一条邻边置位 -> 该角已被那条未置位边的通长带子挖掉，什么都不做 —— 于是连续
      地形的直边收成一条**通长直线**；
    - 两条邻边都没置位 -> 把中心方块在这个角上的直角向内削成半径 MARGIN 的圆角
      （带子的端头读成半圆）。

    为什么必须做减法：一条左右接通的地形带，上下两边都未置位，挖掉上下两条通长带子后
    剩下的就是通长直边。先前从中心方块做加法，直边两端必然各留一个角缺口，一排瓦片连
    起来读成城齿 / 云朵 —— `selfcheck()` 的接缝契约钉的就是这一类错误。
    """
    g = [[True] * TILE for _ in range(TILE)]
    lo, hi = MARGIN, TILE - MARGIN
    if not bits & N:
        _clear_rows(g, 0, lo)
    if not bits & S:
        _clear_rows(g, hi, TILE)
    if not bits & W:
        _clear_cols(g, 0, lo)
    if not bits & E:
        _clear_cols(g, hi, TILE)
    for bit, (ix, iy) in CORNER_INNER.items():
        ex, ey = CORNER_EDGES[bit]
        sides = bool(bits & ex) + bool(bits & ey)
        if sides == 2:
            if not bits & bit:
                _corner_disc(g, *CORNER_OUTER[bit], fill=False)   # 基底从外角圆滑凸进来
        elif sides == 0:
            _cut_corner(g, ix, iy)                              # 带子端头向内削圆
    return g


def _clear_rows(g, y0, y1):
    for y in range(y0, y1):
        for x in range(TILE):
            g[y][x] = False


def _clear_cols(g, x0, x1):
    for y in range(TILE):
        for x in range(x0, x1):
            g[y][x] = False


def _corner_disc(g, cx, cy, fill):
    """以 (cx, cy) 为圆心、半径 MARGIN 的四分之一圆盘，只作用于所属的那个角方格。"""
    lo, hi = MARGIN, TILE - MARGIN
    xs = range(0, lo) if cx <= lo else range(hi, TILE)
    ys = range(0, lo) if cy <= lo else range(hi, TILE)
    for y in ys:
        for x in xs:
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            if dx * dx + dy * dy <= MARGIN * MARGIN:
                g[y][x] = fill


def _cut_corner(g, ix, iy):
    """中心方块在这个角上的直角削成半径 MARGIN 的圆角（只削内侧）。"""
    sx = 1 if ix == MARGIN else -1
    sy = 1 if iy == MARGIN else -1
    ox, oy = ix + sx * MARGIN, iy + sy * MARGIN
    for y in range(TILE):
        for x in range(TILE):
            if not (0 <= (x - ix) * sx < MARGIN and 0 <= (y - iy) * sy < MARGIN):
                continue
            dx, dy = x + 0.5 - ox, y + 0.5 - oy
            if dx * dx + dy * dy > MARGIN * MARGIN:
                g[y][x] = False


# ---------------------------------------------------------------- 边界着色

def _bfs_depth(mask, inside):
    """从边界出发数到内部第几像素，用于"离岸越远水越深"。"""
    depth = [[-1] * TILE for _ in range(TILE)]
    frontier = []
    for y in range(TILE):
        for x in range(TILE):
            if mask[y][x] == inside:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < TILE and 0 <= ny < TILE and mask[ny][nx] == inside \
                        and depth[ny][nx] < 0:
                    depth[ny][nx] = 1
                    frontier.append((nx, ny))
    step = 1
    while frontier:
        step += 1
        nxt = []
        for x, y in frontier:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < TILE and 0 <= ny < TILE and mask[ny][nx] == inside \
                        and depth[ny][nx] < 0:
                    depth[ny][nx] = step
                    nxt.append((nx, ny))
        frontier = nxt
    return depth


def _outward(mask, x, y):
    """边界像素朝外法线（4 邻域里落在另一侧的像素的反方向和）。"""
    ox = oy = 0
    here = mask[y][x]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < TILE and 0 <= ny < TILE) or mask[ny][nx] != here:
            ox += dx
            oy += dy
    return ox, oy


# ---------------------------------------------------------------- 瓦片渲染
#
# 一块 47-blob 瓦片 = 基底材质 + 叠加材质 + 边界语言。边界语言按块查表：
#   wet  基底侧接触线（草被踩暗 / 沙被浸湿 / 草被投上投影）
#   lit  叠加侧朝上朝左的受光边
#   rim  叠加侧朝下朝右的背光边
# 水块不走这套：它的边界是浪花线，内部按"离岸深度"分档。

TERRAIN_TABLE = {
    'dirt':  (mat_dirt, mat_grass, 'h', 'd', 'k'),
    'sand':  (mat_sand, mat_grass, 'h', 's', 'n'),
    'water': (mat_water, mat_sand, 'N', 'w', 'V'),
    'rock':  (mat_rock, mat_grass, 'h', 'r', 'T'),
}


def base_tile(terrain, phase=0, seed=0):
    """整格纯材质，没有叠加区也没有边界 —— 掩码 0 是"孤立小岛"，不能拿它当纯底砖。"""
    mat = {'grass': mat_grass, 'dirt': mat_dirt, 'sand': mat_sand,
           'rock': mat_rock, 'water': mat_water}[terrain]
    return [[mat(x, y, seed) if terrain != 'water'
             else mat_water(x, y, phase, 9, seed) for x in range(TILE)]
            for y in range(TILE)]


def render_tile(block, bits, phase=0, seed=0):
    """一张 47-blob 瓦片：先铺基底材质，再画叠加区与边界。"""
    mask = mask_for(bits)
    over_mat, base_mat, wet, lit, rim = TERRAIN_TABLE[block]
    # 到边界的距离：叠加侧用来分档水深 / 找受光面，基底侧用来铺接触线与投影
    od = _bfs_depth(mask, True)
    bd = _bfs_depth(mask, False)

    rows = []
    for y in range(TILE):
        row = []
        for x in range(TILE):
            ox, oy = _outward(mask, x, y)
            facing_up = oy < 0 or (oy == 0 and ox < 0)
            if mask[y][x]:
                if od[y][x] == 1:                       # 叠加区第一圈像素 = 边界
                    row.append(_water_px(x, y, phase, True, 0) if block == 'water'
                               else lit if facing_up else rim)
                elif block == 'water':
                    row.append(_water_px(x, y, phase, False, od[y][x]))
                elif block == 'rock':
                    row.append('r' if (od[y][x] == 2 and facing_up)
                               else mat_rock(x, y, seed))
                else:
                    row.append(over_mat(x, y, seed))
            elif bd[y][x] == 1:                         # 基底贴着叠加区
                row.append(wet)
            elif block == 'water' and bd[y][x] == 2:
                row.append('N')                         # 湿沙带：越靠外越接近干沙
            elif block == 'rock' and bd[y][x] == 2 and y > 0 and bd[y - 1][x] == 1:
                row.append('H')                         # 投影只往下方铺一格
            else:
                row.append(base_mat(x, y, seed))
        rows.append(row)
    return rows


def _water_px(x, y, phase, edge, depth):
    """浪花线沿边界走，随相位平移；横向周期 8，整除 32 所以平铺无缝。"""
    if edge:
        return 'w' if (x + 2 * phase) % 8 < 5 else 'W'
    return mat_water(x, y, phase, depth)


# ---------------------------------------------------------------- 物件

PROP_GLYPHS = {}          # name -> (grid, anchor) 在 _props() 里填


def _blank():
    return [['.'] * TILE for _ in range(TILE)]


def _put(g, x, y, c):
    if 0 <= x < TILE and 0 <= y < TILE:
        g[y][x] = c


def _shadow(g, cx, cy, rx, ry, c='H'):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                if g[y % TILE][x % TILE] == '.':
                    _put(g, x, y, c)


def _disc(g, cx, cy, rad, fill, hi=None, dark=None):
    for y in range(cy - rad, cy + rad + 1):
        for x in range(cx - rad, cx + rad + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= rad * rad:
                c = fill
                if dark is not None and d2 > (rad - 1.5) ** 2:
                    c = dark
                if hi is not None and (x - cx) + (y - cy) * 1.2 <= -rad * 0.75:
                    c = hi
                _put(g, x, y, c)


def _outline(g, c='o'):
    src = [row[:] for row in g]
    for y in range(TILE):
        for x in range(TILE):
            if src[y][x] != '.':
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < TILE and 0 <= ny < TILE and src[ny][nx] != '.':
                    g[y][x] = c
                    break


PROP_NAMES = ['tree_a', 'tree_b', 'tree_stump', 'bush_a', 'bush_b', 'rock_a', 'rock_b',
              'flower_y', 'flower_p', 'flower_b', 'tuft_a', 'tuft_b',
              'reed_a', 'reed_b', 'lily', 'mush_a', 'mush_b', 'log',
              'fence_h', 'fence_v', 'fence_ne', 'fence_end', 'pebble', 'crack']


def _props():
    for n in PROP_NAMES:
        PROP_GLYPHS[n] = _blank()

    g = PROP_GLYPHS['tree_a']
    _shadow(g, 16, 28, 8, 3)
    _put(g, 15, 20, 'u'), _put(g, 16, 20, 'U'), _put(g, 15, 21, 'u'), _put(g, 16, 21, 'U')
    _put(g, 15, 22, 'u'), _put(g, 16, 22, 'U'), _put(g, 15, 23, 'u'), _put(g, 16, 23, 'U')
    _disc(g, 16, 13, 9, 'G', 'g', 'h')
    _disc(g, 10, 16, 5, 'G', 'g', 'h')
    _disc(g, 22, 16, 5, 'G', None, 'h')
    _outline(g)

    g = PROP_GLYPHS['tree_b']
    _shadow(g, 16, 29, 6, 2)
    for y in range(18, 29):
        _put(g, 15, y, 'u'), _put(g, 16, y, 'U')
    _disc(g, 16, 11, 7, 'e', 'G', 'o')
    _disc(g, 16, 9, 5, 'G', 'g', 'h')
    _outline(g)

    g = PROP_GLYPHS['tree_stump']
    _shadow(g, 16, 26, 7, 3)
    for y in range(19, 27):
        for x in range(10, 22):
            _put(g, x, y, 'u' if x < 16 else 'U')
    _disc(g, 16, 19, 6, 'd', 's', 'k')
    for x in range(11, 22):
        _put(g, x, 19, 'K' if x % 4 == 0 else '.')
    _outline(g)

    g = PROP_GLYPHS['bush_a']
    _shadow(g, 16, 27, 8, 3)
    _disc(g, 12, 21, 6, 'G', 'g', 'h')
    _disc(g, 20, 22, 6, 'G', 'g', 'h')
    _disc(g, 16, 17, 5, 'g', 'g', 'G')
    _outline(g)

    g = PROP_GLYPHS['bush_b']
    _shadow(g, 16, 27, 7, 3)
    _disc(g, 16, 21, 7, 'h', 'G', 'H')
    _disc(g, 14, 18, 4, 'G', 'g', 'h')
    _outline(g)

    g = PROP_GLYPHS['rock_a']
    _shadow(g, 16, 27, 8, 3)
    for y in range(15, 27):
        for x in range(7, 25):
            if ((x - 16) / 9) ** 2 + ((y - 21) / 6) ** 2 <= 1.0:
                _put(g, x, y, 'R')
    for y in range(15, 21):
        for x in range(9, 23):
            if ((x - 16) / 7) ** 2 + ((y - 19) / 4) ** 2 <= 1.0:
                _put(g, x, y, 'r')
    for x in range(8, 24):
        _put(g, x, 26, 'T')
    _outline(g)

    g = PROP_GLYPHS['rock_b']
    _shadow(g, 12, 26, 5, 2)
    _shadow(g, 22, 27, 4, 2)
    _disc(g, 12, 22, 5, 'R', 'r', 't')
    _disc(g, 22, 24, 3, 'R', 'r', 't')
    _outline(g)

    for name, petal, heart in (('flower_y', 'f', 'M'), ('flower_p', 'F', 'f'),
                               ('flower_b', 'b', 'M')):
        g = PROP_GLYPHS[name]
        for cx, cy in ((11, 14), (20, 18), (15, 23)):
            _put(g, cx, cy + 3, 'e')
            _put(g, cx, cy + 4, 'e')
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, 1)):
                _put(g, cx + dx, cy + dy, petal)
            _put(g, cx, cy, heart)

    for name, tilt in (('tuft_a', 0), ('tuft_b', 1)):
        g = PROP_GLYPHS[name]
        for i, (cx, h) in enumerate(((10, 5), (15, 8), (20, 6), (25, 4))):
            lean = 1 if (i + tilt) % 2 else -1
            for k in range(h):                          # 一叶：根部两格宽，向梢部收
                _put(g, cx + lean * (k // 3), 26 - k, 'h' if k < 2 else 'G')
                _put(g, cx + lean * (k // 3) + 1, 26 - k, 'h' if k < 2 else 'e')
            _put(g, cx + lean * ((h - 1) // 3), 27 - h, 'g')

    for name, extra in (('reed_a', 4), ('reed_b', 0)):
        g = PROP_GLYPHS[name]
        for i, (cx, h, lean) in enumerate(((8, 15 + extra, -1), (13, 19 + extra, 0),
                                           (19, 13 + extra, 1), (24, 17, 0))):
            for k in range(h):                          # 越往梢越往外弯
                x = cx + lean * (k * k // (h * 4))
                _put(g, x, 26 - k, 'e' if k % 4 == 0 else 'G')
                _put(g, x + 1, 26 - k, 'e')
            tip = cx + lean * ((h - 1) * (h - 1) // (h * 4))
            _put(g, tip, 27 - h, 'd')                   # 穗头
            _put(g, tip + 1, 26 - h, 'K')

    g = PROP_GLYPHS['lily']
    for y in range(10, 24):
        for x in range(6, 27):
            if ((x - 16) / 10) ** 2 + ((y - 17) / 7) ** 2 <= 1.0:
                _put(g, x, y, 'p')
    for y in range(10, 18):
        for x in range(14, 19):
            _put(g, x, y, '.')
    for y in range(11, 17):
        for x in range(7, 26):
            if ((x - 16) / 9) ** 2 + ((y - 16) / 5) ** 2 <= 1.0:
                _put(g, x, y, 'G')
    _put(g, 20, 14, 'F'), _put(g, 21, 14, 'F'), _put(g, 20, 15, 'f'), _put(g, 21, 15, 'M')

    for name, cap in (('mush_a', 'm'), ('mush_b', 'd')):
        g = PROP_GLYPHS[name]
        for cx, r in ((12, 5), (20, 4)):
            _put(g, cx, 24, 'M'), _put(g, cx, 25, 'M'), _put(g, cx + 1, 24, 'M')
            for y in range(24 - r, 24):
                for x in range(cx - r, cx + r + 1):
                    if ((x - cx) / r) ** 2 + ((y - (24 - r + 1)) / (r * 0.9)) ** 2 <= 1.0:
                        _put(g, x, y, cap)
            for x in range(cx - r + 1, cx + r):
                _put(g, x, 24 - r, 'f' if cap == 'm' else 's')
        _outline(g)

    g = PROP_GLYPHS['log']
    _shadow(g, 16, 24, 10, 3)
    for y in range(17, 24):
        for x in range(5, 27):
            _put(g, x, y, 'u' if y < 20 else 'U')
    _disc(g, 25, 20, 4, 'd', 's', 'k')
    for y in range(17, 24):
        _put(g, 5, y, 'U')
    _outline(g)

    g = PROP_GLYPHS['fence_h']
    for x in (7, 16, 25):
        for y in range(14, 27):
            _put(g, x, y, 'u' if x % 3 else 'U')
    for x in range(6, 27):
        _put(g, x, 17, 'u'), _put(g, x, 18, 'U'), _put(g, x, 22, 'u'), _put(g, x, 23, 'U')
    _outline(g)

    g = PROP_GLYPHS['fence_v']
    for y in (7, 16, 25):
        for x in range(14, 20):
            _put(g, x, y, 'u')
    for y in range(6, 27):
        _put(g, 16, y, 'u'), _put(g, 17, y, 'U')
    _outline(g)

    g = PROP_GLYPHS['fence_ne']
    for y in range(14, 27):
        _put(g, 25, y, 'u'), _put(g, 24, y, 'U')
    for x in range(6, 26):
        _put(g, x, 15, 'u'), _put(g, x, 16, 'U')
    _outline(g)

    g = PROP_GLYPHS['fence_end']
    for y in range(13, 27):
        _put(g, 15, y, 'u'), _put(g, 16, y, 'U')
    _put(g, 14, 13, 'u'), _put(g, 17, 13, 'U')
    _outline(g)

    g = PROP_GLYPHS['pebble']
    _disc(g, 12, 20, 3, 'R', 'r', 't')
    _disc(g, 19, 22, 2, 'R', 'r', 't')
    _outline(g)

    g = PROP_GLYPHS['crack']
    for i, (x, y) in enumerate([(10, 12), (11, 13), (12, 14), (13, 15), (13, 16),
                                (14, 17), (15, 18), (16, 19), (17, 20), (18, 21)]):
        _put(g, x, y, 'K')
    for (x, y) in [(12, 16), (13, 17), (14, 18), (17, 17), (18, 16)]:
        _put(g, x, y, 'k')


_props()


def render_prop(name):
    return [row[:] for row in PROP_GLYPHS[name]]


# ---------------------------------------------------------------- 图集布局

BLOCKS = ['dirt', 'sand', 'water', 'rock']
SPARE = 47                      # 每块第 48 槽：全置位（interior）的第二变体
VARIANT_ROW = 16
PROP_ROWS = (17, 18)
ROWS = 19
SHEET_W = COLS * TILE
SHEET_H = ROWS * TILE


def slot_of(block_index, bits):
    """47 块按掩码升序排进 4 行 x 12 列；第 48 槽留给变体 B。"""
    i = CONFIGS.index(bits)
    row = block_index * 4 + i // COLS
    return row, i % COLS


def variant_slots():
    """第 16 行：4 种地形的 interior 变体 A、4 张草地变体、4 种地形的 interior 变体 C。

    变体 B 在每个块自己的第 48 槽（见 tile_for_slot），所以这里不重复它。
    """
    return ([(b, 0) for b in BLOCKS]
            + [('grass', s) for s in range(4)]
            + [(b, 2) for b in BLOCKS])


def tile_for_slot(row, col, phase=0):
    idx = row * COLS + col
    if row < 16:
        bi, local = divmod(idx, 48)
        block = BLOCKS[bi]
        if local < 47:
            return render_tile(block, CONFIGS[local], phase, 0)
        return base_tile(block, phase, 1)                # interior 变体 B
    if row == VARIANT_ROW:
        terrain, seed = variant_slots()[col]
        return base_tile(terrain, phase, seed)
    pi = (row - PROP_ROWS[0]) * COLS + col
    return render_prop(PROP_NAMES[pi])


# 只有水块（第 8-11 行）与水的 interior 变体（第 16 行第 0、8 槽）随相位变化
ANIMATED_ROWS = frozenset({8, 9, 10, 11})
WATER = BLOCKS.index('water')
ANIMATED_VARIANT_COLS = frozenset({WATER, WATER + 4 + 4})


def sheet_frame(phase=0):
    """整张图集的一帧。"""
    canvas = [['.'] * SHEET_W for _ in range(SHEET_H)]
    for row in range(ROWS):
        for col in range(COLS):
            anim = row in ANIMATED_ROWS or (row == VARIANT_ROW
                                            and col in ANIMATED_VARIANT_COLS)
            tile = tile_for_slot(row, col, phase if anim else 0)
            for y in range(TILE):
                for x in range(TILE):
                    canvas[row * TILE + y][col * TILE + x] = tile[y][x]
    return canvas


# ---------------------------------------------------------------- 场景

BLOCK_FOR_TERRAIN = {'dirt': 'dirt', 'sand': 'sand', 'water': 'water', 'rock': 'rock'}


# 层叠关系：水画在沙之上，所以沙的 blob 不会被身边的水切断（水下仍然是沙）。
COVERS = {'sand': {'water'}}
# 每块叠加地形自己的基底材质 —— 图集里 dirt/sand/rock 铺在草上，水铺在沙上。
BASE_OF = {'dirt': 'grass', 'sand': 'grass', 'water': 'sand', 'rock': 'grass'}


def adjacency_ok(a, b):
    """两种地形能不能直接相邻 = 图集里有没有对应的过渡砖（缺砖就是不完整）。"""
    return (a == b
            or b in COVERS.get(a, ())
            or a in COVERS.get(b, ())
            or BASE_OF.get(a) == b
            or BASE_OF.get(b) == a)


def bits_at(grid, tx, ty, cols, rows):
    """按 8 邻居算出该格自身地形的位掩码。"""
    mine = grid[ty][tx]

    def carries(x, y):
        if not (0 <= x < cols and 0 <= y < rows):
            return mine == 'grass'
        other = grid[y][x]
        return other == mine or other in COVERS.get(mine, ())

    b = 0
    for bit, (dx, dy) in ((N, (0, -1)), (E, (1, 0)), (S, (0, 1)), (W, (-1, 0)),
                          (NE, (1, -1)), (SE, (1, 1)), (SW, (-1, 1)), (NW, (-1, -1))):
        if carries(tx + dx, ty + dy):
            b |= bit
    # 角位只有在相邻两边都置位时才有意义，多余的角位按"填成方形"处理
    for bit, (a, c) in CORNER_EDGES.items():
        if not (b & a and b & c):
            b &= ~bit
    return b


SCENE_COLS, SCENE_ROWS = 24, 16


def scene_map():
    """手工设计的地形图：草地为底，一条斜土路、右下角圆角池塘（沙岸 + 水）、两堆岩石。

    图集只支持"叠加地形 ↔ 它的基底"和"水 ↔ 沙"这两类相邻（见 COVERS / BASE_OF），
    所以三种地形的团块之间必须至少隔一格草地 —— selfcheck 会把越界的相邻对点出来。
    """
    g = [['grass'] * SCENE_COLS for _ in range(SCENE_ROWS)]

    for x in range(1, SCENE_COLS):
        y0 = 2 + x // 8                       # 每 8 列下沉一格，走出斜向透视
        for y in (y0, y0 + 1):
            if 0 <= y < SCENE_ROWS:
                g[y][x] = 'dirt'

    for y in range(SCENE_ROWS):
        for x in range(SCENE_COLS):
            deep = ((x - 17) / 3.6) ** 2 + ((y - 13.2) / 1.9) ** 2
            shore = ((x - 17) / 5.6) ** 2 + ((y - 13.2) / 3.0) ** 2
            if deep < 1.0:
                g[y][x] = 'water'
            elif shore < 2.3:
                g[y][x] = 'sand'
            if ((x - 4) / 2.2) ** 2 + ((y - 12.5) / 1.3) ** 2 < 1.0:
                g[y][x] = 'rock'
            if ((x - 7) / 1.6) ** 2 + ((y - 7.5) / 1.2) ** 2 < 1.0:
                g[y][x] = 'rock'
    return g


# 每类物件只允许出现在这些地形上：芦苇要长在水边、睡莲要漂在水上、树不能长在河里。
PROP_TERRAIN_OK = {
    'tree_a': {'grass'}, 'tree_b': {'grass'}, 'tree_stump': {'grass'},
    'bush_a': {'grass'}, 'bush_b': {'grass'},
    'rock_a': {'grass', 'dirt'}, 'rock_b': {'grass', 'dirt'},
    'flower_y': {'grass'}, 'flower_p': {'grass'}, 'flower_b': {'grass'},
    'tuft_a': {'grass', 'dirt'}, 'tuft_b': {'grass', 'dirt'},
    'reed_a': {'sand'}, 'reed_b': {'sand'}, 'lily': {'water'},
    'mush_a': {'grass'}, 'mush_b': {'grass'}, 'log': {'grass'},
    'fence_h': {'grass'}, 'fence_v': {'grass'}, 'fence_ne': {'grass'},
    'fence_end': {'grass'},
    'pebble': {'grass', 'dirt', 'sand'}, 'crack': {'dirt'},
}


SCENE_PROPS = [
    (1, 6, 'tree_a'), (5, 1, 'tree_b'), (10, 1, 'tree_a'), (13, 6, 'tree_b'),
    (22, 2, 'tree_a'), (23, 7, 'tree_b'),
    (2, 10, 'bush_a'), (9, 10, 'bush_b'), (12, 7, 'bush_a'), (5, 10, 'bush_b'),
    (3, 8, 'flower_y'), (6, 4, 'flower_p'), (11, 8, 'flower_b'), (19, 7, 'flower_y'),
    (1, 13, 'flower_p'), (2, 8, 'mush_a'), (20, 8, 'mush_b'),
    (14, 8, 'tuft_a'), (21, 8, 'tuft_b'), (5, 5, 'tuft_a'), (7, 4, 'tuft_b'),
    (12, 11, 'reed_a'), (22, 11, 'reed_b'), (16, 10, 'reed_a'), (19, 15, 'reed_b'),
    (17, 13, 'lily'), (15, 13, 'lily'),
    (11, 2, 'log'), (10, 5, 'pebble'), (14, 12, 'pebble'),
    (9, 3, 'crack'), (18, 5, 'crack'),
    (0, 9, 'fence_end'), (1, 9, 'fence_h'), (2, 9, 'fence_h'), (3, 9, 'fence_h'),
    (4, 9, 'fence_ne'), (4, 10, 'fence_v'),
]


def scene_frame(phase=0):
    """按 blob 查表把地形图铺成像素：证明 47 块矩阵真的够用，缺砖立刻暴露。"""
    terr = scene_map()
    canvas = [['.'] * (SCENE_COLS * TILE) for _ in range(SCENE_ROWS * TILE)]
    used = {}
    for ty in range(SCENE_ROWS):
        for tx in range(SCENE_COLS):
            t = terr[ty][tx]
            if t == 'grass':
                # 草地按位置哈希挑 4 张变体之一，打散大面积重复感
                tile = base_tile('grass', 0, _h(tx, ty, 17) % 4)
            else:
                bits = bits_at(terr, tx, ty, SCENE_COLS, SCENE_ROWS)
                used.setdefault(BLOCK_FOR_TERRAIN[t], set()).add(bits)
                if bits == 255:
                    # 四面同地形 = interior，按位置哈希在 A/B/C 三张变体里挑一张，
                    # 大面积同材质才不会看出复制粘贴
                    tile = base_tile(t, phase, _h(tx, ty, 29) % 3)
                else:
                    row, col = slot_of(BLOCKS.index(BLOCK_FOR_TERRAIN[t]), bits)
                    tile = tile_for_slot(row, col, phase)
            for y in range(TILE):
                for x in range(TILE):
                    canvas[ty * TILE + y][tx * TILE + x] = tile[y][x]
    for px, py, name in SCENE_PROPS:
        tile = render_prop(name)
        for y in range(TILE):
            for x in range(TILE):
                if tile[y][x] != '.':
                    canvas[py * TILE + y][px * TILE + x] = tile[y][x]
    scene_frame.used_configs = used
    return canvas


# ---------------------------------------------------------------- 校验与导出

def grid_lua(matrix, title):
    used = {c for row in matrix for c in row if c != '.'}
    unknown = used - set(PAL)
    if unknown:
        raise ValueError(f"未在调色板里的字符: {sorted(unknown)}")
    palette = ", ".join(f'{c} = "{PAL[c]}"' for c in sorted(used))
    rows = ",\n  ".join('"%s"' % "".join(r) for r in matrix)
    return f"-- {title}\nreturn {{\n  palette = {{ {palette} }},\n  rows = {{\n  {rows},\n  }},\n}}\n"


def manifest():
    slots = []
    for bi, b in enumerate(BLOCKS):
        for i, bits in enumerate(CONFIGS):
            slots.append({"index": (bi * 48 + i), "row": bi * 4 + i // COLS,
                          "col": i % COLS, "block": b, "bits": bits,
                          "hex": f"0x{bits:02X}", "variant": "a",
                          "animated": b == "water"})
        slots.append({"index": bi * 48 + 47, "row": bi * 4 + 3, "col": 11,
                      "block": b, "bits": None, "hex": None, "variant": "b",
                      "kind": "interior", "animated": b == "water"})
    for k, (terrain, seed) in enumerate(variant_slots()):
        slots.append({"index": VARIANT_ROW * COLS + k, "row": VARIANT_ROW, "col": k,
                      "block": terrain, "bits": None, "hex": None,
                      "variant": "abc"[seed] if seed < 3 else str(seed),
                      "kind": "interior", "animated": terrain == "water"})
    for k, name in enumerate(PROP_NAMES):
        row, col = PROP_ROWS[0] + k // COLS, k % COLS
        slots.append({"index": row * COLS + col, "row": row, "col": col,
                      "block": "prop", "name": name, "bits": None, "animated": False})
    return {"tile": TILE, "margin": MARGIN, "cols": COLS, "rows": ROWS,
            "bitmask": {"N": 1, "E": 2, "S": 4, "W": 8, "NE": 16, "SE": 32, "SW": 64,
                        "NW": 128},
            "configs": len(CONFIGS), "water_phases": WATER_PHASES,
            "palette": PAL, "slots": slots}


def selfcheck():
    """不启动 Aseprite 也能跑的结构性校验：砖数、几何、接缝、相位、调色板。"""
    problems = []

    if len(set(CONFIGS)) != 47:
        problems.append(f"blob 配置数 {len(set(CONFIGS))} != 47")

    # 几何两端：全置位铺满整格；空掩码是孤立小岛，一个像素都不许碰瓦片边界
    if not all(all(mask_for(255)[y]) for y in range(TILE)):
        problems.append("bits=0xFF 没铺满 32x32")
    iso = mask_for(0)
    if any(iso[0]) or any(iso[-1]) or any(row[0] or row[-1] for row in iso):
        problems.append("bits=0x00 的孤立块碰到了瓦片边界，平铺会连成一片")

    # 调色板字符必须是合法 Lua 标识符（paint_grid 的数据文件用它当键），且不能是 '.'
    bad = [c for c in PAL if not c.isalpha()]
    if bad:
        problems.append(f"非法调色板键: {bad}")

    # 接缝契约：同地形左右相邻的两张砖，共享边界**中段**（去掉两个 M×M 角区）必须
    # 逐像素同覆盖 —— 差一个像素就会在地图上露出一条穿过地形内部的缝。
    # 两端角区允许有限出入：blob 的角位由"该角的两侧邻居"决定，当地形边界正好在相邻
    # 两格之间出现 T 形岔口时，两块砖各自看到的对角格不是同一个，几像素的凹口是
    # 47-blob 方案的固有近似（Godot / Tiled 的 blob 同样如此），不是几何 bug。
    # 阈值 8 = 单侧角区 8 像素宽的一行，超过它就是真的画错了。
    terr = scene_map()
    worst = 0

    def seam(tag, a_line, b_line):
        nonlocal worst
        mid = [i for i in range(TILE) if MARGIN <= i < TILE - MARGIN]
        if [a_line[i] for i in mid] != [b_line[i] for i in mid]:
            problems.append(f"{tag} 中段覆盖不连续")
        worst = max(worst, sum(1 for i in range(TILE)
                               if (i < MARGIN or i >= TILE - MARGIN)
                               and a_line[i] != b_line[i]))

    for ty in range(SCENE_ROWS):
        for tx in range(SCENE_COLS - 1):
            if terr[ty][tx] != terr[ty][tx + 1] or terr[ty][tx] == 'grass':
                continue
            a = mask_for(bits_at(terr, tx, ty, SCENE_COLS, SCENE_ROWS))
            b = mask_for(bits_at(terr, tx + 1, ty, SCENE_COLS, SCENE_ROWS))
            seam(f"横向接缝 ({tx},{ty})/({tx + 1},{ty})",
                 [row[-1] for row in a], [row[0] for row in b])
    for ty in range(SCENE_ROWS - 1):
        for tx in range(SCENE_COLS):
            if terr[ty][tx] != terr[ty + 1][tx] or terr[ty][tx] == 'grass':
                continue
            a = mask_for(bits_at(terr, tx, ty, SCENE_COLS, SCENE_ROWS))
            b = mask_for(bits_at(terr, tx, ty + 1, SCENE_COLS, SCENE_ROWS))
            seam(f"纵向接缝 ({tx},{ty})/({tx},{ty + 1})", a[-1], b[0])
    if worst > 8:
        problems.append(f"角区接缝凹口过大：最大 {worst} 像素（阈值 8）")
    selfcheck.worst_corner = worst

    # 场景里出现的每种地形对，图集必须有对应的过渡砖
    for ty in range(SCENE_ROWS):
        for tx in range(SCENE_COLS):
            t = terr[ty][tx]
            for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
                nx, ny = tx + dx, ty + dy
                if not (0 <= nx < SCENE_COLS and 0 <= ny < SCENE_ROWS):
                    continue
                if not adjacency_ok(t, terr[ny][nx]):
                    problems.append(f"({tx},{ty}){t} 与 ({nx},{ny}){terr[ny][nx]} "
                                    f"相邻，但图集里没有这对过渡砖")

    # 水动画：4 帧必须两两不同（否则 GIF 编码器会合并帧）
    hashes = {json.dumps(sheet_frame(p)) for p in range(WATER_PHASES)}
    if len(hashes) != WATER_PHASES:
        problems.append(f"水相位只有 {len(hashes)}/{WATER_PHASES} 种不同")

    # 物件：非空、且槽位放得下
    if len(PROP_NAMES) > (ROWS - PROP_ROWS[0]) * COLS:
        problems.append("物件数量超出图集行数")
    for name in PROP_NAMES:
        if all(c == '.' for row in render_prop(name) for c in row):
            problems.append(f"物件 {name} 是空的")

    seen_props = set()
    for px, py, name in SCENE_PROPS:
        if not (0 <= px < SCENE_COLS and 0 <= py < SCENE_ROWS):
            problems.append(f"物件 {name} 放在场景外 ({px},{py})")
            continue
        if (px, py) in seen_props:
            problems.append(f"两个物件抢同一格 ({px},{py})")
        seen_props.add((px, py))
        if terr[py][px] not in PROP_TERRAIN_OK[name]:
            problems.append(f"物件 {name} 放在 {terr[py][px]} 上 ({px},{py})，"
                            f"只允许 {'/'.join(sorted(PROP_TERRAIN_OK[name]))}")
    return problems


def preview_png(path: Path):
    """本地判图用的 2x 预览，不是交付物（交付物由 Aseprite 导出）。"""
    from PIL import Image
    frame = sheet_frame(0)
    img = Image.new("RGBA", (SHEET_W, SHEET_H), (28, 30, 36, 255))
    for y in range(SHEET_H):
        for x in range(SHEET_W):
            c = frame[y][x]
            if c != '.':
                h = PAL[c]
                img.putpixel((x, y), tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    img.save(path)
    scene = Image.new("RGBA", (SCENE_COLS * TILE, SCENE_ROWS * TILE), (0, 0, 0, 0))
    sm = scene_frame(0)
    for y in range(SCENE_ROWS * TILE):
        for x in range(SCENE_COLS * TILE):
            c = sm[y][x]
            if c != '.':
                h = PAL[c]
                scene.putpixel((x, y), tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    scene.save(path.with_name("scene_preview.png"))
    return img.size


if __name__ == "__main__":
    probs = selfcheck()
    print(f"blob configs: {len(CONFIGS)}, atlas {SHEET_W}x{SHEET_H} "
          f"({ROWS} rows x {COLS} cols), palette {len(PAL)} colors, "
          f"worst corner seam {selfcheck.worst_corner}px")
    for p in probs:
        print("  FAIL:", p)
    if probs:
        raise SystemExit(f"selfcheck: {len(probs)} 个问题")
    print("selfcheck: 全绿")
    here = Path(__file__).parent / ".build"
    here.mkdir(exist_ok=True)
    print("preview:", preview_png(here / "atlas_preview.png"))
