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
from collections import Counter
from pathlib import Path

TILE = 32
# 内缩量就是转角的圆弧半径：8（四分之一格）在 32px 上会把直边读成一串半圆，
# 整片地形像云朵；6 只留下"这块地形圆了个角"的感觉。
MARGIN = 6
JITTER = 2                        # 地形边界相对 MARGIN 线的漂移幅度（±像素）
WATER_PHASES = 4
COLS = 12

# ---------------------------------------------------------------- 调色板
#
# 一张会互相借色的盘，不是五条各自封闭的坡。锚点是星露谷 / Cute Fantasy 那类田园向：
# 阳光暖、暗部冷。每条色阶都**同时改明度和色相** —— 暗端往蓝紫挪、亮端往黄橙挪，
# 只拉亮度叫直色阶，铺开来就是廉价塑料。
#
# 跨材质共用的三档是刻意的：'z' 冷紫阴影同时是土、沙、石三者的暗端过渡，
# 'y' 暖米高光同时是沙与土的受光顶面，'o' 是全部硬物件的描边。借色让五种地形
# 放进同一张图后像一家人，而不是五张贴纸。

PAL = {
    # 草地：暗端偏冷的深绿 -> 亮端偏黄的受光草尖
    'H': "#2A5A45",   # 最深（冷绿，带一点青）
    'h': "#3E7C3F",   # 暗
    'G': "#63A83F",   # 主色
    'g': "#8FCA55",   # 亮
    'p': "#BEE07E",   # 受光草尖（暖黄绿）
    # 泥土路：紫黑阴影 -> 暖棕 -> 米黄受光
    'K': "#332639",   # 最深（紫黑）
    'k': "#6B4527",   # 中间暗棕：'K' 到 'D' 跨度太大，路面色斑需要这一档
    'z': "#4A3B57",   # 共用冷紫阴影（土 / 沙 / 石都借它）
    'D': "#8A5E3A",   # 主色
    'd': "#B0804E",   # 亮
    'N': "#D2A469",   # 受光顶面
    # 沙：紫灰湿沙 -> 暖米
    'Q': "#6B5566",   # 最深（紫灰）
    'q': "#9A7F6B",   # 暗
    'S': "#CFAE78",   # 主色
    's': "#E8CD93",   # 亮
    'y': "#F7E7B4",   # 共用暖米高光（沙 / 土都借它）
    # 水：深蓝紫底 -> 青 -> 近白浪花
    'V': "#16395E",   # 最深
    'v': "#2A6A9E",   # 暗
    'W': "#4E9BC9",   # 主色
    'w': "#8FD6E8",   # 浅水 / 受光
    'f': "#D2F2F8",   # 浪花
    # 石：冷蓝灰，暗部借共用紫
    'T': "#2C2B3D",   # 最深
    't': "#565C72",   # 暗（冷）
    'R': "#8A90A2",   # 主色
    'r': "#BAC1CD",   # 亮
    # 硬物件描边
    'o': "#221C2B",
    # 物件专属
    'e': "#2F6B34",   # 树冠最深
    'u': "#7A4B2A",   # 树干
    'U': "#4E2E18",   # 树干暗
    'm': "#C4483F",   # 蘑菇伞
    'M': "#EFE0C4",   # 蘑菇柄
    'b': "#7FA8E8",   # 蓝花
    'F': "#F27D9B",   # 粉花
    'j': "#F2D14E",   # 黄花（'f' 已经是浪花色，别混用）
}

# ---------------------------------------------------------------- 噪声

_MASK32 = 0xFFFFFFFF


def _h(x, y, seed):
    v = (x * 374761393 + y * 668265263 + seed * 1442695041) & _MASK32
    v = ((v ^ (v >> 13)) * 1274126177) & _MASK32
    return (v ^ (v >> 16)) & _MASK32


def _u01(x, y, seed):
    return _h(x, y, seed) / _MASK32


def _smooth1d(u, period, seed):
    """一维平滑噪声（smoothstep 插值），周期整除 TILE。

    给地形边界和铺石砖缝加漂移用：周期对齐保证相邻瓦片在交界处最多差 1px，
    于是弯得起来又不会在接缝处断掉。
    """
    n = TILE // period
    i = int(u) % n
    j = (i + 1) % n
    f = (u % period) / period
    f = f * f * (3 - 2 * f)
    return _u01(i, 0, seed) * (1 - f) + _u01(j, 0, seed) * f


def _clump(x, y, cell, seed, every):
    """格点哈希决定"这一格里有没有一撮笔触"，撮的位置在格内随机偏移。

    笔触不钉死在 `x % 8 == 3` 这类固定列上 —— 那会让整片材质出现明显的竖直方向性，
    而教程口径是"纹理需无明显方向性"。cell 取 TILE 的约数、偏移限制在格内，所以无缝。
    """
    w = TILE // cell
    cx, cy = (x // cell) % w, (y // cell) % w
    if _h(cx, cy, seed) % every:
        return None
    ox = _h(cx, cy, seed + 1) % cell
    oy = _h(cx, cy, seed + 2) % cell
    dx, dy = x % cell - ox, y % cell - oy
    if dx == 0 and dy == 0:
        return "dot"
    if dx == 0 and dy == -1:
        return "tail"
    return None


# ---------------------------------------------------------------- 材质
#
# 每种材质 3-5 档：低频场决定哪块受光、哪块背光（大色块，不是噪点），`_clump` 撒可辨认
# 的笔触（草叶、砂砾、裂缝）。主色要厚、过渡色要薄；两档之间不要铺成等宽色带。

_FIELDS = {}


def _blob_field(seed, cells=2):
    """撒 cells*cells 个**半径各不相同**的圆心，像素按"离最近圆心扣除该圆半径"取值。

    两件事缺一不可：
    - 值噪声在格点上只能画**轴对齐的矩形**，拿它分档铺出来是棋盘格（路面踩过）；
    - 等半径的圆团虽然圆了，但大小一致、按格点排，读起来是豹纹而不是地皮。
    所以每个圆心带自己的半径（哈希取 0.45-1.15 倍步长），取"最近圆心距离 - 该圆半径"
    的最小值：负值在团内、正值在团外，边界因此既有大有小、还会互相吞并。
    距离按瓦片取模算，团块在边界处自然绕回去，平铺无缝。整场按 (seed, cells) 缓存。
    """
    key = (seed, cells)
    if key in _FIELDS:
        return _FIELDS[key]
    step = TILE // cells
    pts = []
    for cy in range(cells):
        for cx in range(cells):
            jx = _h(cx, cy, seed) % step
            jy = _h(cx, cy, seed + 1) % step
            rad = step * (0.45 + 0.7 * _u01(cx, cy, seed + 3))
            pts.append(((cx * step + jx) % TILE, (cy * step + jy) % TILE, rad))
    grid = [[0.0] * TILE for _ in range(TILE)]
    for y in range(TILE):
        for x in range(TILE):
            best = 999.0
            for px, py, rad in pts:
                dx = min(abs(x - px), TILE - abs(x - px))
                dy = min(abs(y - py), TILE - abs(y - py))
                d = (dx * dx + dy * dy) ** 0.5 - rad
                if d < best:
                    best = d
            grid[y][x] = best
    flat = sorted(v for row in grid for v in row)
    lo, hi = flat[0], flat[-1] or 1.0
    grid = [[(v - lo) / (hi - lo) for v in row] for row in grid]
    _FIELDS[key] = grid
    return grid


_CUTS = {}


def _cuts_for(seed, pcts, cells):
    """该材质那场团块场的分位阈值，按 (seed, 比例, 圆心密度) 缓存一次。"""
    key = (seed, pcts, cells)
    cuts = _CUTS.get(key)
    if cuts is None:
        vs = sorted(v for row in _blob_field(seed, cells) for v in row)
        cuts = [vs[min(int(p * len(vs)), len(vs) - 1)] for p in pcts]
        _CUTS[key] = cuts
    return cuts


def _soft_tier(x, y, seed, pcts, tones, cells=2, eps=0.030):
    """按分位数分档 + 色块交界收一层主色边。

    两件事都是被门禁/看图逼出来的：
    - **分位数**：同一套手调阈值在不同种子下差别极大（泥土那场值噪声实测只铺在
      0.36-0.59），固定阈值会让材质 98% 落进同一档，读成一块纯色；
    - **收边**：连续场里"离阈值很近"的像素恰好就是色斑轮廓，把它们涂成主色，
      等于给每个色斑描一圈 1-2px 过渡带 —— 教程口径的"过渡色薄"，也是
      硬切边和"画过"的唯一区别。
    """
    cuts = _cuts_for(seed, pcts, cells)
    v = _blob_field(seed, cells)[y][x]
    if any(abs(v - c) < eps for c in cuts):
        return tones[len(tones) // 2]
    return tones[sum(1 for c in cuts if v >= c)]


def mat_grass(x, y, seed=0):
    c = _soft_tier(x, y, seed, (0.06, 0.62), ('h', 'G', 'g'))
    k = _clump(x, y, 4, seed + 31, 4)
    if k == "dot":
        c = 'p'
    elif k == "tail":
        c = 'h'
    return c


def mat_dirt(x, y, seed=0):
    """三档：暗档 'k' 是踩实的低洼，亮档 'd' 是凸起，主色占六成。

    两个坑都踩过：给到四档并把阈值切在值噪声格点上，相邻格子明暗交替，路面铺出来是
    棋盘格；暗档直接用 'K'（紫黑）又太跳，读成一坑一坑的洞 —— 中间需要 'k' 这一档暖棕。
    更亮的部分交给 `_clump` 的砂砾点，不靠加档位。
    """
    c = _soft_tier(x, y, seed + 101, (0.08, 0.70), ('k', 'D', 'd'))
    k = _clump(x, y, 4, seed + 211, 7)
    if k == "dot":
        c = 'N'
    elif k == "tail":
        c = 'z'
    return c


def mat_sand(x, y, seed=0):
    c = _soft_tier(x, y, seed + 307, (0.08, 0.66), ('q', 'S', 's'))
    # 风成波纹：只有一三分之二的条带起浪，且"哪一行起浪"随列漂移 ——
    # 每 8 行一道等长亮线会读成灯芯绒。
    cell = _h((x // 8) % 4, (y // 8) % 4, seed + 353)
    if cell % 3 == 0 and y % 8 == cell % 8:
        c = 'y' if (x // 8) % 2 else 's'
    return c


def mat_water(x, y, phase=0, depth=0, seed=0):
    """水陆过渡只留"近岸两格浅水"这一档，其余一律主色。

    深水若单独分档，就必须和 interior 砖完全相同，否则在岸砖与 interior 砖的交界处会
    横出一条与地形无关的硬线；而两三格宽的河永远到不了那个深度，照样出线。
    所以深度只用来决定"亮"，不用来决定"暗"。
    """
    c = 'w' if depth == 2 else 'W'
    cell = _h((x // 8) % 4, (y // 8) % 4, seed + 911)
    if cell % 3 == 2:
        return c                                    # 三分之一的条带不起浪，才不像刻度尺
    # 浪头所在的那一行随条带漂移；固定 y%8==3/4 会让亮暗线排成一张网格
    if y % 8 == cell % 8:
        if (x + phase * 4) % 16 < 3 + cell % 3:
            return 'f' if cell % 2 else 'w'
    if y % 8 == (cell + 1) % 8 and (x + phase * 4) % 16 < 2 + cell % 2:
        return 'v'
    return c


def mat_rock(x, y, seed=0):
    c = _soft_tier(x, y, seed + 503, (0.12, 0.72), ('t', 'R', 'r'), cells=3)
    # 铺石：16x8 的砖，缝线本身按平滑噪声左右漂移，读得出"一块块铺"而不是灰噪点。
    # 缝只占一条，不再给缝上高光 —— 高光 + 三档面色 + 裂纹叠起来会把主色吃光。
    jx = (x + int(round(2 * _smooth1d(y, 8, seed + 531) - 1))) % 16
    jy = (y + int(round(2 * _smooth1d(x, 8, seed + 541) - 1))) % 8
    if jx == 0 or jy == 0:
        c = 't'
    if _clump(x, y, 8, seed + 601, 9) == "dot":
        c = 'T'
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
    if not bits & N:
        _clear_edge(g, 'N', bits)
    if not bits & S:
        _clear_edge(g, 'S', bits)
    if not bits & W:
        _clear_edge(g, 'W', bits)
    if not bits & E:
        _clear_edge(g, 'E', bits)
    for bit, (ix, iy) in CORNER_INNER.items():
        ex, ey = CORNER_EDGES[bit]
        sides = bool(bits & ex) + bool(bits & ey)
        if sides == 2:
            if not bits & bit:
                _corner_disc(g, *CORNER_OUTER[bit], fill=False)   # 基底从外角圆滑凸进来
        elif sides == 0:
            _cut_corner(g, ix, iy)                              # 带子端头向内削圆
    return g


EDGE_SEED = {'N': 9001, 'E': 9002, 'S': 9003, 'W': 9004}


def _clear_edge(g, edge, bits):
    """沿边挖掉宽 MARGIN 的通长带，但带边本身按平滑噪声漂移 ±JITTER 像素。

    抖动曲线只按"哪条边"取种子、不按位掩码取，所以相邻两砖在同一条边上看到的是同一条
    曲线，交界处最多差 1px；否则每块砖各抖各的，铺开后边界会被接缝切断。
    """
    seed = EDGE_SEED[edge]
    for u in range(TILE):
        off = MARGIN + int(round((2 * _smooth1d(u, 16, seed) - 1) * JITTER))
        off = max(1, min(TILE - 1, off))
        if edge == 'N':
            for y in range(off):
                g[y][u] = False
        elif edge == 'S':
            for y in range(TILE - off, TILE):
                g[y][u] = False
        elif edge == 'W':
            for x in range(off):
                g[u][x] = False
        else:
            for x in range(TILE - off, TILE):
                g[u][x] = False


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
# 一块 47-blob 瓦片 = 基底材质 + 叠加材质 + 边界语言。查表给六种角色：
#   wet   基底贴着叠加区的那一圈（草被踩暗 / 沙被浸湿 / 草被投上投影）
#   lit   叠加区边界中朝上朝左的受光边
#   rim   叠加区边界中朝下朝右的背光边
#   poke  基底往叠加区里戳的笔触（草叶戳进土路）—— 边界不规整的关键
#   grit  叠加区往基底外撒的碎屑（路缘的砂砾）
# 水块的边界是浪花线，内部按"离岸距离"分档。

TERRAIN_TABLE = {
    'dirt':  (mat_dirt, mat_grass, 'h', 'N', 'z', 'G', 'K'),
    'sand':  (mat_sand, mat_grass, 'h', 'y', 'q', 'G', 'q'),
    'water': (mat_water, mat_sand, 'q', 'f', 'v', 'w', 'v'),
    'rock':  (mat_rock, mat_grass, 'H', 'r', 'T', 'g', 'T'),
}


def base_tile(terrain, phase=0, seed=0):
    """整格纯材质，没有叠加区也没有边界 —— 掩码 0 是"孤立小岛"，不能拿它当纯底砖。"""
    mat = {'grass': mat_grass, 'dirt': mat_dirt, 'sand': mat_sand,
           'rock': mat_rock, 'water': mat_water}[terrain]
    return [[mat(x, y, seed) if terrain != 'water'
             else mat_water(x, y, phase, 9, seed) for x in range(TILE)]
            for y in range(TILE)]


def _pokes(x, y, every, seed):
    """边界笔触的取舍用逐像素哈希：周期就是瓦片本身，所以平铺仍然无缝。

    频率刻意低：一撮草叶戳进土路，是"几根"而不是"一圈噪点"—— 25% 的撒盐读起来是
    边界脏了，不是边界有机。
    """
    return _h(x, y, seed) % every == 0


def render_tile(block, bits, phase=0, seed=0):
    """一张 47-blob 瓦片：先铺基底材质，再画叠加区、边界与互相侵入的笔触。"""
    mask = mask_for(bits)
    over_mat, base_mat, wet, lit, rim, poke, grit = TERRAIN_TABLE[block]
    # 到边界的距离：叠加侧用来找受光面与分档水深，基底侧用来铺接触线与投影
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
                    if _pokes(x, y, 9, seed + 7001):
                        row.append(poke)                # 草叶戳进叠加区
                    elif block == 'water':
                        row.append(_water_px(x, y, phase, True, 0))
                    else:
                        row.append(lit if facing_up else rim)
                elif od[y][x] == 2 and _pokes(x, y, 11, seed + 7001):
                    row.append(poke)                    # 同一撮草叶往里有第二节
                elif block == 'water':
                    row.append(_water_px(x, y, phase, False, od[y][x]))
                elif block == 'rock':
                    row.append('r' if (od[y][x] == 2 and facing_up)
                               else mat_rock(x, y, seed))
                else:
                    row.append(over_mat(x, y, seed))
            elif bd[y][x] == 1:                         # 基底贴着叠加区
                row.append(grit if _pokes(x, y, 7, seed + 7003) else wet)
            elif block == 'water' and bd[y][x] == 2:
                row.append('q')                         # 湿沙带：越靠外越接近干沙
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
#
# 物件和地面共用一张盘、同一套光：每个团块都是「高光 / 亮面 / 主色 / 暗部」四档，
# 左上受光、右下收暗，暗部一律借那几档共用冷色（'z' / 'q' / 'H'），所以树和石头
# 放进新地面里才是一家人。描边只包本体，接触投影画在描边之外且只落在空格上 ——
# 先描边再补影，否则投影会被描一圈黑边。

PROP_GLYPHS = {}


def _blank():
    return [['.'] * TILE for _ in range(TILE)]


def _put(g, x, y, c):
    if 0 <= x < TILE and 0 <= y < TILE:
        g[y][x] = c


def _under(g, x, y, c):
    """只往空像素上画（接触投影用），不覆盖已经画好的本体。"""
    if 0 <= x < TILE and 0 <= y < TILE and g[y][x] == '.':
        g[y][x] = c


def _ball(g, cx, cy, rad, dark, mid, light, hi=None, squash=1.0):
    """一个左上受光的团块：沿光向把四档铺开，右下最外一圈收成暗边。"""
    for y in range(cy - rad - 1, cy + rad + 2):
        for x in range(cx - rad - 1, cx + rad + 2):
            dx, dy = x - cx, (y - cy) / squash
            if dx * dx + dy * dy > rad * rad:
                continue
            t = (dx + dy) / (rad * 1.42)               # -1（左上）.. +1（右下）
            if hi is not None and t < -0.45:
                c = hi
            elif t < 0.18:
                c = light
            elif t < 0.60:
                c = mid
            else:
                c = dark
            if dx * dx + dy * dy > (rad - 1.2) ** 2 and t > 0.1:
                c = dark
            _put(g, x, y, c)


def _blade(g, x, y, h, lean, tone, tip=None):
    """一根草叶/芦苇：根部两格宽，往梢部收成一格并侧移。"""
    for k in range(h):
        yy = y - k
        xx = x + lean * (k * k // max(h * 3, 1))
        _put(g, xx, yy, tone if k < h - 1 else (tip or tone))
        if k < h - 2:
            _put(g, xx + 1, yy, tone)


def _contact(g, cx, cy, rx, ry, c='H'):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                _under(g, x, y, c)


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


def _bark(g, x0, y0, w, h):
    """树干：左缘借土的受光色，中间木色，右侧借最深紫当背光。"""
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            _put(g, x, y, 'd' if x == x0 else ('u' if x < x0 + w - 1 else 'U'))
    _put(g, x0, y0 + h - 1, 'U')
    _put(g, x0 + w - 1, y0 + h - 1, 'U')


PROP_NAMES = ['tree_a', 'tree_b', 'tree_stump', 'bush_a', 'bush_b', 'rock_a', 'rock_b',
              'flower_y', 'flower_p', 'flower_b', 'tuft_a', 'tuft_b',
              'reed_a', 'reed_b', 'lily', 'mush_a', 'mush_b', 'log',
              'fence_h', 'fence_v', 'fence_ne', 'fence_end', 'pebble', 'crack']


def _tree(g, cx, top, rad, trunk_h):
    """阔叶树：树冠是 1 主团 + 2 侧团，树干带根脚收口。"""
    _bark(g, cx - 1, top + rad, 3, trunk_h)
    _ball(g, cx - 5, top + rad - 3, 5, 'H', 'h', 'G', 'g')
    _ball(g, cx + 5, top + rad - 3, 5, 'H', 'h', 'G', 'g')
    _ball(g, cx, top + rad, rad, 'H', 'h', 'G', 'p')


def _stone(g, cx, cy, rx, ry):
    """石头：顶面亮、正面主色、底缘一圈暗色，靠棱面而不是靠描边读体积。"""
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 > 1.0:
                continue
            if y < cy - ry * 0.35:
                c = 'r'
            elif y > cy + ry * 0.45 or x > cx + rx * 0.5:
                c = 't'
            else:
                c = 'R'
            _put(g, x, y, c)
    for x in range(cx - rx + 2, cx + rx - 1):
        _put(g, x, cy - ry + 1, 'r')
    _put(g, cx - 1, cy - 1, 'T')
    _put(g, cx, cy + 1, 'T')


def _flower(g, seeds, petal, heart):
    for cx, cy in seeds:
        _put(g, cx, cy + 3, 'h')
        _put(g, cx, cy + 4, 'h')
        _put(g, cx + 1, cy + 4, 'H')
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            _put(g, cx + dx, cy + dy, petal)
        _put(g, cx - 1, cy - 1, petal)
        _put(g, cx + 1, cy + 1, 'q' if petal == 'j' else 'z')
        _put(g, cx, cy, heart)


def _props():
    for name in PROP_NAMES:
        PROP_GLYPHS[name] = _blank()

    g = PROP_GLYPHS['tree_a']
    _tree(g, 16, 6, 9, 12)
    _outline(g)
    _contact(g, 16, 28, 10, 3)

    g = PROP_GLYPHS['tree_b']
    _bark(g, 15, 15, 3, 12)
    _ball(g, 16, 17, 5, 'H', 'h', 'G', 'g')
    _ball(g, 12, 14, 4, 'H', 'h', 'G', 'g')
    _ball(g, 20, 14, 4, 'H', 'h', 'G', 'g')
    _ball(g, 16, 10, 7, 'H', 'h', 'G', 'p')
    _outline(g)
    _contact(g, 16, 28, 8, 3)

    g = PROP_GLYPHS['tree_stump']
    for y in range(18, 27):
        for x in range(10, 23):
            if ((x - 16) / 6.5) ** 2 + ((y - 22) / 5.5) ** 2 <= 1.0:
                _put(g, x, y, 'u' if x < 14 else ('U' if x > 19 else 'u'))
    _ball(g, 16, 18, 6, 'z', 'd', 'N', 'y', squash=0.45)
    for r, c in ((4, 'd'), (2, 'K')):
        for x in range(16 - r, 16 + r + 1):
            _put(g, x, 18, c)
    _blade(g, 21, 20, 5, 1, 'G', 'p')
    _outline(g)
    _contact(g, 16, 27, 8, 2)

    for name, cx, cy, rad in (('bush_a', 16, 21, 6), ('bush_b', 15, 22, 5)):
        g = PROP_GLYPHS[name]
        _ball(g, cx - 5, cy + 1, rad - 2, 'H', 'h', 'G', 'g')
        _ball(g, cx + 5, cy + 1, rad - 2, 'H', 'h', 'G', 'g')
        _ball(g, cx, cy - 1, rad, 'H', 'h', 'G', 'p')
        _put(g, cx - 3, cy - 3, 'F')
        _put(g, cx + 4, cy + 1, 'F')
        _outline(g)
        _contact(g, cx, cy + rad + 1, rad + 2, 2)

    g = PROP_GLYPHS['rock_a']
    _stone(g, 16, 21, 9, 6)
    _stone(g, 9, 23, 4, 3)
    _outline(g)
    _contact(g, 16, 27, 10, 2)

    g = PROP_GLYPHS['rock_b']
    _stone(g, 12, 22, 5, 4)
    _stone(g, 21, 24, 4, 3)
    _outline(g)
    _contact(g, 12, 26, 6, 2)
    _contact(g, 21, 27, 5, 2)

    _flower(PROP_GLYPHS['flower_y'], ((11, 14), (20, 18), (15, 23)), 'j', 'M')
    _flower(PROP_GLYPHS['flower_p'], ((12, 15), (20, 20)), 'F', 'y')
    _flower(PROP_GLYPHS['flower_b'], ((11, 13), (19, 18), (15, 23)), 'b', 'M')

    for name, tilt in (('tuft_a', 1), ('tuft_b', -1)):
        g = PROP_GLYPHS[name]
        for i, (cx, h) in enumerate(((9, 5), (13, 8), (17, 6), (21, 9), (25, 5))):
            _blade(g, cx, 26, h, tilt if i % 2 else -tilt,
                   'G' if i % 2 else 'h', 'p')
        _contact(g, 17, 27, 9, 2)

    for name, extra in (('reed_a', 4), ('reed_b', 0)):
        g = PROP_GLYPHS[name]
        for i, (cx, h, lean) in enumerate(((8, 15 + extra, -1), (13, 19 + extra, 0),
                                           (19, 13 + extra, 1), (24, 17, 0))):
            _blade(g, cx, 26, h, lean, 'e' if i % 2 else 'h', 'G')
            _blade(g, cx + 1, 26, h - 4, lean, 'G', 'p')
            _put(g, cx + lean * ((h - 1) // 4), 27 - h, 'd')
            _put(g, cx + lean * ((h - 1) // 4) + 1, 26 - h, 'K')
        _contact(g, 16, 27, 11, 2)

    g = PROP_GLYPHS['lily']
    _ball(g, 16, 17, 10, 'H', 'h', 'G', 'p', squash=0.62)
    for y in range(9, 16):
        for x in range(15, 20):
            if (x - 16) >= (16 - y):
                _put(g, x, y, '.')
    _ball(g, 21, 14, 3, 'z', 'F', 'j', 'y')
    _outline(g)

    for name, cap, spot in (('mush_a', 'm', 'M'), ('mush_b', 'D', 'N')):
        g = PROP_GLYPHS[name]
        for cx, r, dy in ((12, 5, 0), (20, 4, 2)):
            _put(g, cx, 25 + dy // 2, 'M')
            _put(g, cx + 1, 25 + dy // 2, 'q')
            for y in range(24 - r + dy, 24 + dy):
                for x in range(cx - r, cx + r + 1):
                    if ((x - cx) / r) ** 2 + ((y - (24 - r + dy + 1)) / (r * 0.95)) ** 2 > 1.0:
                        continue
                    _put(g, x, y, 'F' if (x - cx) + (y - (24 - r + dy)) < -r else cap)
            _put(g, cx - r + 2, 24 - r + dy + 2, spot)
            _put(g, cx + 1, 24 - r + dy + 2, spot)
            _put(g, cx - 1, 24 + dy, 'z')
            _put(g, cx, 24 + dy, 'z')
        _outline(g)
        _contact(g, 16, 27, 9, 2)

    g = PROP_GLYPHS['log']
    for y in range(17, 25):
        for x in range(5, 27):
            if ((x - 16) / 11) ** 2 + ((y - 21) / 4) ** 2 <= 1.0:
                _put(g, x, y, 'd' if y < 19 else ('u' if y < 22 else 'U'))
    _ball(g, 25, 21, 4, 'K', 'd', 'N', 'y', squash=1.1)
    for x in (6, 9, 14, 19):
        _put(g, x, 22, 'U')
        _put(g, x, 23, 'U')
    _outline(g)
    _contact(g, 16, 26, 11, 2)

    def post(g, x, y0=13, y1=27):
        for y in range(y0, y1):
            _put(g, x, y, 'd' if y < y0 + 1 else 'u')
            _put(g, x + 1, y, 'u' if y < y1 - 2 else 'U')
            _put(g, x + 2, y, 'U')

    def rail(g, x0, x1, y):
        for x in range(x0, x1):
            _put(g, x, y, 'd')
            _put(g, x, y + 1, 'u')
            _put(g, x, y + 2, 'U')

    g = PROP_GLYPHS['fence_h']
    rail(g, 5, 27, 16)
    rail(g, 5, 27, 21)
    for px in (6, 15, 24):
        post(g, px)
    _outline(g)
    _contact(g, 16, 27, 11, 2)

    g = PROP_GLYPHS['fence_v']
    for py in (6, 15, 24):
        for x in range(14, 19):
            _put(g, x, py, 'd' if x < 16 else 'U')
            _put(g, x, py + 1, 'u' if x < 17 else 'U')
    for y in range(6, 27):
        _put(g, 15, y, 'd')
        _put(g, 16, y, 'u')
        _put(g, 17, y, 'U')
    _outline(g)
    _contact(g, 16, 27, 5, 2)

    g = PROP_GLYPHS['fence_ne']
    rail(g, 5, 25, 15)
    for py in (14, 20):
        for x in range(24, 27):
            _put(g, x, py, 'd')
            _put(g, x, py + 1, 'u')
    post(g, 24)
    _outline(g)
    _contact(g, 16, 27, 10, 2)

    g = PROP_GLYPHS['fence_end']
    post(g, 14)
    _put(g, 13, 13, 'd')
    _put(g, 17, 13, 'U')
    rail(g, 5, 15, 17)
    _outline(g)
    _contact(g, 15, 27, 7, 2)

    g = PROP_GLYPHS['pebble']
    _stone(g, 12, 20, 4, 3)
    _stone(g, 19, 23, 3, 2)
    _outline(g)
    _contact(g, 12, 23, 5, 1)

    g = PROP_GLYPHS['crack']
    for x, y in ((9, 11), (10, 12), (11, 13), (12, 14), (13, 15), (13, 16),
                 (14, 17), (15, 18), (16, 19), (17, 20), (18, 21), (19, 22)):
        _put(g, x, y, 'K')
        _put(g, x + 1, y, 'z')
        _put(g, x, y - 1, 'N')
    for x, y in ((11, 16), (12, 17), (13, 18), (17, 16), (18, 15)):
        _put(g, x, y, 'K')
        _put(g, x, y - 1, 'N')


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


def _hsv(hexs):
    r, g, b = (int(hexs[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        h = 0.0
    elif mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60, (0 if mx == 0 else d / mx), mx


def _hue_arc(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def emitted(terrain, seed=0):
    """一种材质**实际发到画布上的颜色**，按明度从暗到亮排。

    门禁量的是这个，不是某张手写的"色阶表" —— 表和代码会各说各话：声明里写了四档、
    实际铺出来是一个纯色，正是上一版审查里 dirt/rock 的情况，声明自己看不出来。
    """
    chars = set()
    for row in base_tile(terrain, 0, seed):
        chars |= set(row) - {'.'}
    if terrain in TERRAIN_TABLE:
        for bits in (0, N, N | E, N | E | NE, N | S, N | E | S | W, 255):
            for row in render_tile(terrain, bits, 0, seed):
                chars |= set(row) - {'.'}
    return sorted(chars, key=lambda c: _hsv(PAL[c])[2])


MATERIALS = ("grass", "dirt", "sand", "water", "rock")


def art_audit():
    """把"像不像手画的"变成会失败的断言。

    逐条对着市面教程口径：色阶要色相偏移（暗端偏冷、亮端偏暖，跨度 >=10°，只拉亮度
    叫直色阶）、一张盘要互相借色（多条独立坡放进同一张图会打架，像贴纸）、分界线要
    参差（不能整片落在同一条直线上）、纹理要无明显方向性（笔触不许挤在同一列）、
    主色之下还得留有可辨认的细节（非主色 >=8%，否则是平涂）、大面积不许一款重复到
    一眼看穿。
    """
    problems = []
    ramps = {}

    for terrain in MATERIALS:
        ramp = emitted(terrain)
        ramps[terrain] = set(ramp)
        if len(ramp) < 3:
            problems.append(f"{terrain} 只发出 {len(ramp)} 档颜色 {ramp}，读成一块纯色")
            continue
        hs = [_hsv(PAL[c])[0] for c in ramp]
        spread = max(_hue_arc(hs[0], h) for h in hs[1:])
        if spread < 10:
            problems.append(f"{terrain} 色阶只改了明度：实际发出的 {ramp} 色相跨度 "
                            f"{spread:.0f}° < 10°（直色阶）")

    names = list(ramps)
    borrowed = [(a, b, sorted(ramps[a] & ramps[b]))
                for i, a in enumerate(names) for b in names[i + 1:]
                if len(ramps[a] & ramps[b]) >= 2]
    if len(borrowed) < 2:
        problems.append(f"材质之间不借色：只有 {len(borrowed)} 对共用 >=2 档（需要 >=2 对）")

    straight = total = 0
    for bits in CONFIGS:
        if bits & N:
            continue                                # 上边接通，这里压根没有边界，不算"规整"
        m = mask_for(bits)
        for x in range(TILE):
            col = [y for y in range(TILE) if m[y][x]]
            if not col or min(col) == 0:
                continue
            total += 1
            if min(col) == MARGIN:
                straight += 1
    ratio = straight / max(total, 1)
    if ratio > 0.5:
        problems.append(f"边界太规整：{ratio:.0%} 的边界列落在零抖动的直线上（应 <=50%）")

    for name, primary in (("grass", 'G'), ("dirt", 'D'), ("sand", 'S'), ("rock", 'R')):
        grid = base_tile(name, 0, 0)
        hist = Counter(c for row in grid for c in row)
        off = [(x, y) for y in range(TILE) for x in range(TILE) if grid[y][x] != primary]
        if not off:
            problems.append(f"{name} 是纯色平涂：没有任何细节像素")
            continue
        share = len(off) / (TILE * TILE)
        if share < 0.08:
            problems.append(f"{name} 细节不足：非主色像素只占 {share:.0%}（应 8%-55%）")
        elif share > 0.55:
            problems.append(f"{name} 细节过密：非主色占 {share:.0%}，主色撑不住画面，"
                            f"铺开是一片碎噪（应 8%-55%）")
        top = hist.most_common(1)[0]
        if top[1] / (TILE * TILE) < 0.45:
            problems.append(f"{name} 没有主色：最多的一档 '{top[0]}' 只占 "
                            f"{top[1] / (TILE * TILE):.0%}（应 >=45%）")
        cols = Counter(x for x, _ in off)
        worst = cols.most_common(1)[0][1] / len(off)
        if worst > 0.5:
            problems.append(f"{name} 纹理有方向性：{worst:.0%} 的笔触挤在同一列")

    terr = scene_map()
    placements = Counter()
    for ty in range(SCENE_ROWS):
        for tx in range(SCENE_COLS):
            t = terr[ty][tx]
            if t == 'grass':
                placements[('grass', _h(tx, ty, 17) % 4)] += 1
            else:
                placements[(t, bits_at(terr, tx, ty, SCENE_COLS, SCENE_ROWS))] += 1
    top = placements.most_common(1)[0]
    if top[1] / (SCENE_COLS * SCENE_ROWS) > 0.25:
        problems.append(f"场景重复感：最重复的一款占 {top[1] / (SCENE_COLS * SCENE_ROWS):.0%}")
    return problems


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
        # "中段"必须避开抖动带：边界线本身在 MARGIN +/- JITTER 里游动，那块区域两砖差
        # 一两像素正是要的效果；抖动带之外还差像素，才是真的画错了。
        lo, hi = MARGIN + JITTER, TILE - MARGIN - JITTER
        mid = [i for i in range(TILE) if lo <= i < hi]
        if [a_line[i] for i in mid] != [b_line[i] for i in mid]:
            problems.append(f"{tag} 中段覆盖不连续")
        worst = max(worst, sum(1 for i in range(TILE)
                               if (i < lo or i >= hi) and a_line[i] != b_line[i]))

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

    # 观感门禁：像不像手画的，也变成会失败的断言
    problems += art_audit()
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
