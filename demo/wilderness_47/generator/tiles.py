"""Design model for the wilderness tileset: palette, materials, 47-blob geometry,
boundary shading, atlas and scene.

No Aseprite here -- this only produces character matrices (every character is a
key into PAL, '.' is transparent). produce.py hands the matrices to paint_grid to
put them into Aseprite, then compares them back pixel by pixel.

## The 47-blob construction (the foundation of this atlas)

A tile has 4 edges (N/E/S/W) and 4 corners (NE/SE/SW/NW), 8 neighbour slots in
total. A corner slot only has visual meaning when **both adjacent edges are set**;
otherwise it draws exactly the same as "that corner not set" -- so the corner
subsets allowed for each of the 16 edge combinations add up to exactly 47:

    0 edges 1 + 1 edge 4 + 2 adjacent edges 8 + 2 opposite edges 2 + 3 edges 16
    + 4 edges 16 = 47

Geometry rules (`MARGIN` = inset in pixels, `TILE` = tile side length):

- the centre square [M, T-M]² is always covered by the overlay terrain;
- every set edge pushes the coverage out to the tile border on that side;
- each of the four corner cells picks one of four options:
  **both adjacent edges set and the corner set** -> filled (a right-angle join);
  **both adjacent edges set but the corner not set** -> a quarter disc of radius M
  centred on the corner's inner point (the two bands join via a concave arc);
  **only one adjacent edge set** -> filled (the corner cell is part of that band,
  so the boundary closes as a straight line at the tile edge instead of bulging
  once per cell);
  **neither adjacent edge set** -> left to the base, and the centre square's right
  angle at this corner is cut **inwards** into a radius-M fillet (the band end
  reads as a semicircle).

The "only one adjacent edge" branch was once drawn as an inward fillet, which put a
semicircle bump at each end of a straight edge and made a row of tiles read as a
cogwheel / cloud -- `selfcheck()`'s seam contract exists to pin down exactly this
class of mistake. `blob_configs()` enumerates the 47 bitmasks, `mask_for()`
rasterises them.

## Bitmask convention (this is the number in manifest.json)

    bit0=N  bit1=E  bit2=S  bit3=W  bit4=NE  bit5=SE  bit6=SW  bit7=NW

The atlas is ordered by ascending mask, and the slot number is the row-major index;
when importing into an engine go by the manifest, not by what you guess by eye.
"""

import json
from collections import Counter
from pathlib import Path

TILE = 32
# The inset is also the corner fillet radius: 8 (a quarter tile) makes a straight
# edge read as a string of semicircles on 32px, so the whole terrain looks like a
# cloud; 6 leaves only a "this terrain has a rounded corner" impression.
MARGIN = 6
JITTER = 2                        # boundary drift around the MARGIN line (±px)
WATER_PHASES = 4
COLS = 12

# ---------------------------------------------------------------- palette
#
# One palette that lends colours to itself, not five separate closed ramps. The
# anchor is the pastoral look of Stardew Valley / Cute Fantasy: warm sunlight,
# cool shadows. Every ramp changes **both value and hue** -- the dark end drifts
# towards blue-violet and the light end towards yellow-orange; raising lightness
# alone is a straight ramp, and spread out it looks like cheap plastic.
#
# The three steps shared across materials are deliberate: 'z' cool violet shadow
# is also the dark transition for dirt, sand and stone, 'y' warm cream highlight is
# also the lit top face of sand and dirt, and 'o' is the outline of every hard prop.
# Borrowing colours makes five terrains in one image read as one family rather than
# five stickers.

PAL = {
    # grass: deep green with a cool dark end -> sunlit tips with a yellow light end
    'H': "#2A5A45",   # darkest (cold green, a touch of cyan)
    'h': "#3E7C3F",   # dark
    'G': "#63A83F",   # main
    'g': "#8FCA55",   # light
    'p': "#BEE07E",   # sunlit grass tip (warm yellow-green)
    # dirt path: violet-black shadow -> warm brown -> cream-lit
    'K': "#332639",   # darkest (violet-black)
    'k': "#6B4527",   # mid dark brown: the 'K' -> 'D' jump is too big, path patches need it
    'z': "#4A3B57",   # shared cool violet shadow (dirt / sand / stone borrow it)
    'D': "#8A5E3A",   # main
    'd': "#B0804E",   # light
    'N': "#D2A469",   # lit top face
    # sand: violet-grey wet sand -> warm cream
    'Q': "#6B5566",   # darkest (violet-grey)
    'q': "#9A7F6B",   # dark
    'S': "#CFAE78",   # main
    's': "#E8CD93",   # light
    'y': "#F7E7B4",   # shared warm cream highlight (sand / dirt borrow it)
    # water: deep blue-violet base -> cyan -> near-white foam
    'V': "#16395E",   # darkest
    'v': "#2A6A9E",   # dark
    'W': "#4E9BC9",   # main
    'w': "#8FD6E8",   # shallow water / lit
    'f': "#D2F2F8",   # foam
    # stone: cool blue-grey, the dark end borrows the shared violet
    'T': "#2C2B3D",   # darkest
    't': "#565C72",   # dark (cool)
    'R': "#8A90A2",   # main
    'r': "#BAC1CD",   # light
    # hard prop outline
    'o': "#221C2B",
    # prop-only colours
    'e': "#2F6B34",   # deepest tree canopy
    'u': "#7A4B2A",   # trunk
    'U': "#4E2E18",   # trunk shadow
    'm': "#C4483F",   # mushroom cap
    'M': "#EFE0C4",   # mushroom stem
    'b': "#7FA8E8",   # blue flower
    'F': "#F27D9B",   # pink flower
    'j': "#F2D14E",   # yellow flower ('f' is already foam, do not mix them up)
}

# ---------------------------------------------------------------- noise

_MASK32 = 0xFFFFFFFF


def _h(x, y, seed):
    v = (x * 374761393 + y * 668265263 + seed * 1442695041) & _MASK32
    v = ((v ^ (v >> 13)) * 1274126177) & _MASK32
    return (v ^ (v >> 16)) & _MASK32


def _u01(x, y, seed):
    return _h(x, y, seed) / _MASK32


def _smooth1d(u, period, seed):
    """1D smooth noise (smoothstep interpolation) whose period divides TILE.

    Used to add drift to terrain boundaries and paving joints: aligning the period
    guarantees neighbouring tiles differ by at most 1px at the join, so the edge can
    bend without breaking at the seam.
    """
    n = TILE // period
    i = int(u) % n
    j = (i + 1) % n
    f = (u % period) / period
    f = f * f * (3 - 2 * f)
    return _u01(i, 0, seed) * (1 - f) + _u01(j, 0, seed) * f


def _clump(x, y, cell, seed, every):
    """A lattice hash decides "whether this cell holds a clump of strokes"; the
    clump's position is randomly offset inside the cell.

    Strokes are not pinned to fixed columns like `x % 8 == 3` -- that gives the whole
    material an obvious vertical directionality, while the tutorial standard is
    "texture must show no obvious directionality". cell divides TILE and the offset
    stays inside the cell, so it tiles seamlessly.
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


# ---------------------------------------------------------------- materials
#
# 3-5 steps per material: a low-frequency field decides which patches are lit and
# which are shaded (large colour patches, not noise), and `_clump` scatters
# recognisable strokes (grass blades, grit, cracks). The main colour has to be thick
# and the transition colours thin; never lay two steps out as an even-width band.

_FIELDS = {}


def _blob_field(seed, cells=2):
    """Scatter cells*cells centres **each with its own radius**, and give every pixel
    "distance to the nearest centre minus that centre's radius".

    Both parts are essential:
    - value noise on lattice points can only draw **axis-aligned rectangles**, and
      tiering it produces a chequerboard (tried on the dirt path);
    - equal-radius blobs are round, but all the same size and arranged on lattice
      points, so they read as leopard print rather than ground.
    So every centre carries its own radius (hashed to 0.45-1.15 times the step) and
    we take the minimum of "nearest centre distance - that radius": negative inside a
    blob, positive outside, so boundaries vary in size and blobs also swallow each
    other. Distances are computed modulo the tile, so blobs wrap around the border
    naturally and tile seamlessly. The whole field is cached by (seed, cells).
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
    """Quantile thresholds for that material's blob field, cached once per (seed,
    ratios, centre density)."""
    key = (seed, pcts, cells)
    cuts = _CUTS.get(key)
    if cuts is None:
        vs = sorted(v for row in _blob_field(seed, cells) for v in row)
        cuts = [vs[min(int(p * len(vs)), len(vs) - 1)] for p in pcts]
        _CUTS[key] = cuts
    return cuts


def _soft_tier(x, y, seed, pcts, tones, cells=2, eps=0.030):
    """Tier by quantiles, plus a main-colour edge along each patch boundary.

    Both parts were forced by the gates and by looking at the image:
    - **quantiles**: the same hand-tuned thresholds differ wildly between seeds (the
      dirt field's value noise measured 0.36-0.59), and fixed thresholds put 98% of
      the material into one tier, reading as flat colour;
    - **edge**: in a continuous field the pixels "close to a threshold" are exactly
      the patch outlines; painting them in the main colour gives every patch a 1-2px
      transition band -- the tutorial's "thin transition colours", and the only
      difference between a hard cut and something that looks drawn.
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
    """Three tiers: the dark 'k' is compacted hollows, the light 'd' is raised ground,
    and the main colour takes 60%.

    Both pits have been fallen into: four tiers with thresholds on value-noise
    lattice points alternate light and dark per cell, and the path comes out as a
    chequerboard; using 'K' (violet-black) directly for the dark tier jumps too much
    and reads as a pit full of holes -- the mid warm brown 'k' is needed. The
    brighter detail is left to `_clump`'s grit, not to extra tiers.
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
    # Wind ripples: only one band in three raises a wave, and "which row does"
    # drifts with the column -- an even bright line every 8 rows reads as corduroy.
    cell = _h((x // 8) % 4, (y // 8) % 4, seed + 353)
    if cell % 3 == 0 and y % 8 == cell % 8:
        c = 'y' if (x // 8) % 2 else 's'
    return c


def mat_water(x, y, phase=0, depth=0, seed=0):
    """The water/land transition keeps only one tier, "two cells of shallow water near
    the shore"; everything else is the main colour.

    If deep water got its own tier it would have to be exactly identical to the
    interior tile, otherwise the border between shore and interior tiles grows a hard
    line unrelated to the terrain; yet a river two or three cells wide never reaches
    that depth and still shows the line. So depth only decides "light", never "dark".
    """
    c = 'w' if depth == 2 else 'W'
    cell = _h((x // 8) % 4, (y // 8) % 4, seed + 911)
    if cell % 3 == 2:
        return c                                    # a third of bands raise no wave, not a ruler
    # The row the crest sits on drifts per band; fixing y%8==3/4 lines the light and
    # dark rows up into a grid
    if y % 8 == cell % 8:
        if (x + phase * 4) % 16 < 3 + cell % 3:
            return 'f' if cell % 2 else 'w'
    if y % 8 == (cell + 1) % 8 and (x + phase * 4) % 16 < 2 + cell % 2:
        return 'v'
    return c


def mat_rock(x, y, seed=0):
    c = _soft_tier(x, y, seed + 503, (0.12, 0.72), ('t', 'R', 'r'), cells=3)
    # Paving: 16x8 bricks whose joints themselves drift left/right on smooth noise,
    # so it reads as "laid one by one" rather than grey noise. A joint is one pixel
    # wide and gets no highlight -- highlight + three face tiers + cracks together
    # eat the main colour.
    jx = (x + int(round(2 * _smooth1d(y, 8, seed + 531) - 1))) % 16
    jy = (y + int(round(2 * _smooth1d(x, 8, seed + 541) - 1))) % 8
    if jx == 0 or jy == 0:
        c = 't'
    if _clump(x, y, 8, seed + 601, 9) == "dot":
        c = 'T'
    return c


# ---------------------------------------------------------------- blob geometry

N, E, S, W, NE, SE, SW, NW = 1, 2, 4, 8, 16, 32, 64, 128
CORNER_EDGES = {NE: (N, E), SE: (S, E), SW: (S, W), NW: (N, W)}
CORNER_INNER = {NE: (TILE - MARGIN, MARGIN), SE: (TILE - MARGIN, TILE - MARGIN),
                SW: (MARGIN, TILE - MARGIN), NW: (MARGIN, MARGIN)}
# The "outer corner point" to cut when the corner is unset: the tile's true corner,
# not the corner's inner point
CORNER_OUTER = {NE: (TILE, 0), SE: (TILE, TILE), SW: (0, TILE), NW: (0, 0)}


def blob_configs():
    """The 47 bitmasks, ascending. A corner bit exists only when both adjacent edges
    are set."""
    out = []
    for edges in range(16):
        # A corner bit only means something when both adjacent edges are set;
        # otherwise it draws exactly like "corner unset"
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
    """Bitmask -> 32x32 boolean raster of the overlay area (a pixel centre inside the
    area counts as covered).

    The model is **subtractive**: start from "the whole cell is overlay terrain",
    carve a **full-length** base band MARGIN wide off every edge that is **not** set,
    then fix up each corner:

    - both adjacent edges set, corner set -> leave it, the corner cell stays in the
      overlay (a right-angle join);
    - both adjacent edges set, corner not set -> carve a quarter disc of radius
      MARGIN centred on the tile's **outer corner**: the base bulges in smoothly at
      the corner, which is the blob's "inner corner" tile;
    - exactly one adjacent edge set -> the corner was already carved by the
      full-length band of the unset edge, so do nothing, and the straight edge of a
      continuous terrain closes into a **full-length straight line**;
    - neither adjacent edge set -> cut the centre square's right angle at this corner
      inwards into a radius-MARGIN fillet (the band end reads as a semicircle).

    Why subtraction is required: in a terrain band that runs left to right with both
    the top and bottom edges unset, carving the two full-length bands leaves exactly
    the full-length straight edges. The earlier additive approach starting from the
    centre square always left a notch at each end of a straight edge, and a row of
    tiles read as crenellations / clouds -- that is the class of bug `selfcheck()`'s
    seam contract pins down.
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
                _corner_disc(g, *CORNER_OUTER[bit], fill=False)   # base bulges in at the corner
        elif sides == 0:
            _cut_corner(g, ix, iy)                              # round the band end inwards
    return g


EDGE_SEED = {'N': 9001, 'E': 9002, 'S': 9003, 'W': 9004}


def _clear_edge(g, edge, bits):
    """Carve a full-length band MARGIN wide along an edge, but the band edge itself
    drifts ±JITTER pixels on smooth noise.

    The jitter curve is seeded by "which edge" only, not by the bitmask, so two
    neighbouring tiles see the same curve on the same edge and differ by at most 1px
    at the join; otherwise every tile jitters on its own and the joints cut the
    boundary apart once laid out.
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
    """Quarter disc of radius MARGIN centred on (cx, cy), applied only to the corner
    cell it belongs to."""
    lo, hi = MARGIN, TILE - MARGIN
    xs = range(0, lo) if cx <= lo else range(hi, TILE)
    ys = range(0, lo) if cy <= lo else range(hi, TILE)
    for y in ys:
        for x in xs:
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            if dx * dx + dy * dy <= MARGIN * MARGIN:
                g[y][x] = fill


def _cut_corner(g, ix, iy):
    """Cut the centre square's right angle at this corner into a radius-MARGIN fillet
    (inner side only)."""
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


# ---------------------------------------------------------------- boundary shading

def _bfs_depth(mask, inside):
    """Count pixels inwards from the boundary, for "the further from shore, the
    deeper the water"."""
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
    """Outward normal of a boundary pixel (the negated sum of the 4-neighbour
    directions that fall on the other side)."""
    ox = oy = 0
    here = mask[y][x]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < TILE and 0 <= ny < TILE) or mask[ny][nx] != here:
            ox += dx
            oy += dy
    return ox, oy


# ---------------------------------------------------------------- tile render
#
# A 47-blob tile = base material + overlay material + boundary language. A lookup
# gives six roles:
#   wet   the ring of base hugging the overlay (trodden grass / soaked sand / grass
#         under a cast shadow)
#   lit   the upward/leftward lit edge of the overlay boundary
#   rim   the downward/rightward shaded edge of the overlay boundary
#   poke  a stroke of base poking into the overlay (a blade through the dirt path) --
#         the key to a non-regular boundary
#   grit  crumbs the overlay scatters onto the base (grit along the path edge)
# Water tiles have a foam line as boundary, and are tiered by "distance from shore"
# inside.

TERRAIN_TABLE = {
    'dirt':  (mat_dirt, mat_grass, 'h', 'N', 'z', 'G', 'K'),
    'sand':  (mat_sand, mat_grass, 'h', 'y', 'q', 'G', 'q'),
    'water': (mat_water, mat_sand, 'q', 'f', 'v', 'w', 'v'),
    'rock':  (mat_rock, mat_grass, 'H', 'r', 'T', 'g', 'T'),
}


def base_tile(terrain, phase=0, seed=0):
    """A whole cell of pure material, no overlay and no boundary -- mask 0 is an
    "isolated islet" and must not be used as a plain base tile."""
    mat = {'grass': mat_grass, 'dirt': mat_dirt, 'sand': mat_sand,
           'rock': mat_rock, 'water': mat_water}[terrain]
    return [[mat(x, y, seed) if terrain != 'water'
             else mat_water(x, y, phase, 9, seed) for x in range(TILE)]
            for y in range(TILE)]


def _pokes(x, y, every, seed):
    """Pick boundary strokes with a per-pixel hash: the period is the tile itself, so
    tiling stays seamless.

    Deliberately low frequency: a clump of blades poking into the dirt path is "a few
    blades", not "a ring of noise" -- 25% salting reads as a dirty boundary, not an
    organic one.
    """
    return _h(x, y, seed) % every == 0


def render_tile(block, bits, phase=0, seed=0):
    """One 47-blob tile: lay the base material first, then draw the overlay, its
    boundary and the strokes that invade each other."""
    mask = mask_for(bits)
    over_mat, base_mat, wet, lit, rim, poke, grit = TERRAIN_TABLE[block]
    # Distance to the boundary: the overlay side uses it for lit faces and water
    # depth tiers, the base side for the contact line and the cast shadow.
    od = _bfs_depth(mask, True)
    bd = _bfs_depth(mask, False)

    rows = []
    for y in range(TILE):
        row = []
        for x in range(TILE):
            ox, oy = _outward(mask, x, y)
            facing_up = oy < 0 or (oy == 0 and ox < 0)
            if mask[y][x]:
                if od[y][x] == 1:                       # first ring of overlay = boundary
                    if _pokes(x, y, 9, seed + 7001):
                        row.append(poke)                # a blade pokes into the overlay
                    elif block == 'water':
                        row.append(_water_px(x, y, phase, True, 0))
                    else:
                        row.append(lit if facing_up else rim)
                elif od[y][x] == 2 and _pokes(x, y, 11, seed + 7001):
                    row.append(poke)                    # the same clump continues inwards
                elif block == 'water':
                    row.append(_water_px(x, y, phase, False, od[y][x]))
                elif block == 'rock':
                    row.append('r' if (od[y][x] == 2 and facing_up)
                               else mat_rock(x, y, seed))
                else:
                    row.append(over_mat(x, y, seed))
            elif bd[y][x] == 1:                         # base hugging the overlay
                row.append(grit if _pokes(x, y, 7, seed + 7003) else wet)
            elif block == 'water' and bd[y][x] == 2:
                row.append('q')                         # wet sand band: further out, drier
            elif block == 'rock' and bd[y][x] == 2 and y > 0 and bd[y - 1][x] == 1:
                row.append('H')                         # cast shadow, one cell down only
            else:
                row.append(base_mat(x, y, seed))
        rows.append(row)
    return rows


def _water_px(x, y, phase, edge, depth):
    """The foam line follows the boundary and shifts with the phase; its horizontal
    period is 8, which divides 32, so it tiles seamlessly."""
    if edge:
        return 'w' if (x + 2 * phase) % 8 < 5 else 'W'
    return mat_water(x, y, phase, depth)


# ---------------------------------------------------------------- props
#
# Props and ground share one palette and one light: every blob is four steps
# (highlight / light / main / shadow), lit from the upper left and shaded to the
# lower right, with the shadow always borrowing those shared cool colours
# ('z' / 'q' / 'H'), which is why trees and rocks sit in a new ground as one family.
# The outline wraps the body only; the contact shadow is drawn outside the outline and
# only on empty pixels -- outline first, then shadow, or the shadow itself gets an
# outline.

PROP_GLYPHS = {}


def _blank():
    return [['.'] * TILE for _ in range(TILE)]


def _put(g, x, y, c):
    if 0 <= x < TILE and 0 <= y < TILE:
        g[y][x] = c


def _under(g, x, y, c):
    """Draw only on empty pixels (for the contact shadow), never over the body
    already drawn."""
    if 0 <= x < TILE and 0 <= y < TILE and g[y][x] == '.':
        g[y][x] = c


def _ball(g, cx, cy, rad, dark, mid, light, hi=None, squash=1.0):
    """A blob lit from the upper left: the four steps spread along the light
    direction, and the outer ring at the lower right becomes the dark edge."""
    for y in range(cy - rad - 1, cy + rad + 2):
        for x in range(cx - rad - 1, cx + rad + 2):
            dx, dy = x - cx, (y - cy) / squash
            if dx * dx + dy * dy > rad * rad:
                continue
            t = (dx + dy) / (rad * 1.42)               # -1 (upper left) .. +1 (lower right)
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
    """One blade of grass / reed: two cells wide at the root, tapering to one cell and
    shifting sideways at the tip."""
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
    """Trunk: the left edge borrows dirt's lit colour, the middle is wood, and the
    right side borrows the deepest violet as backlight."""
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
    """Broadleaf tree: the canopy is 1 main blob + 2 side blobs, and the trunk closes
    with a root flare."""
    _bark(g, cx - 1, top + rad, 3, trunk_h)
    _ball(g, cx - 5, top + rad - 3, 5, 'H', 'h', 'G', 'g')
    _ball(g, cx + 5, top + rad - 3, 5, 'H', 'h', 'G', 'g')
    _ball(g, cx, top + rad, rad, 'H', 'h', 'G', 'p')


def _stone(g, cx, cy, rx, ry):
    """Stone: lit top, main colour on the front, a ring of dark along the bottom edge;
    volume comes from facets, not from the outline."""
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


# ---------------------------------------------------------------- atlas layout

BLOCKS = ['dirt', 'sand', 'water', 'rock']
SPARE = 47                      # slot 48 per block: second variant of all-set (interior)
VARIANT_ROW = 16
PROP_ROWS = (17, 18)
ROWS = 19
SHEET_W = COLS * TILE
SHEET_H = ROWS * TILE


def slot_of(block_index, bits):
    """The 47 tiles sorted into 4 rows x 12 columns by ascending mask; slot 48 is left
    for variant B."""
    i = CONFIGS.index(bits)
    row = block_index * 4 + i // COLS
    return row, i % COLS


def variant_slots():
    """Row 16: interior variant A of the 4 terrains, 4 grass variants, interior variant
    C of the 4 terrains.

    Variant B lives in each block's own slot 48 (see tile_for_slot), so it is not
    repeated here.
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
        return base_tile(block, phase, 1)                # interior variant B
    if row == VARIANT_ROW:
        terrain, seed = variant_slots()[col]
        return base_tile(terrain, phase, seed)
    pi = (row - PROP_ROWS[0]) * COLS + col
    return render_prop(PROP_NAMES[pi])


# Only the water block (rows 8-11) and water's interior variants (row 16, slots 0 and
# 8) change with the phase
ANIMATED_ROWS = frozenset({8, 9, 10, 11})
WATER = BLOCKS.index('water')
ANIMATED_VARIANT_COLS = frozenset({WATER, WATER + 4 + 4})


def sheet_frame(phase=0):
    """One frame of the whole atlas."""
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


# ---------------------------------------------------------------- scene

BLOCK_FOR_TERRAIN = {'dirt': 'dirt', 'sand': 'sand', 'water': 'water', 'rock': 'rock'}


# Layering: water is drawn over sand, so sand's blob is not cut by the water next to
# it (the bed under the water is still sand).
COVERS = {'sand': {'water'}}
# Each overlay terrain's own base material -- in the atlas dirt/sand/rock lie on
# grass and water lies on sand.
BASE_OF = {'dirt': 'grass', 'sand': 'grass', 'water': 'sand', 'rock': 'grass'}


def adjacency_ok(a, b):
    """Whether two terrains may touch directly = whether the atlas has a matching
    transition tile (a missing tile means incomplete)."""
    return (a == b
            or b in COVERS.get(a, ())
            or a in COVERS.get(b, ())
            or BASE_OF.get(a) == b
            or BASE_OF.get(b) == a)


def bits_at(grid, tx, ty, cols, rows):
    """Compute the bitmask of the cell's own terrain from its 8 neighbours."""
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
    # A corner bit only means something when both adjacent edges are set; spare
    # corner bits are treated as "fill the square"
    for bit, (a, c) in CORNER_EDGES.items():
        if not (b & a and b & c):
            b &= ~bit
    return b


SCENE_COLS, SCENE_ROWS = 24, 16


def scene_map():
    """A hand-designed terrain map: grass base, one slanted dirt path, a rounded pond
    in the lower right (sand shore + water) and two rock piles.

    The atlas only supports "overlay terrain <-> its base" and "water <-> sand"
    adjacency (see COVERS / BASE_OF), so blobs of three different terrains must be
    separated by at least one grass cell -- selfcheck flags any adjacency pair that
    breaks this.
    """
    g = [['grass'] * SCENE_COLS for _ in range(SCENE_ROWS)]

    for x in range(1, SCENE_COLS):
        y0 = 2 + x // 8                       # drop a row every 8 columns for perspective
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


# Each prop may only appear on these terrains: reeds grow by the water, lilies float
# on it, and trees cannot grow in the river.
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
    """Lay the terrain map out into pixels via the blob lookup: proof that the 47 tiles
    really suffice, so a missing tile shows up at once."""
    terr = scene_map()
    canvas = [['.'] * (SCENE_COLS * TILE) for _ in range(SCENE_ROWS * TILE)]
    used = {}
    for ty in range(SCENE_ROWS):
        for tx in range(SCENE_COLS):
            t = terr[ty][tx]
            if t == 'grass':
                # Grass picks one of 4 variants by position hash, breaking up large-area
                # repetition
                tile = base_tile('grass', 0, _h(tx, ty, 17) % 4)
            else:
                bits = bits_at(terr, tx, ty, SCENE_COLS, SCENE_ROWS)
                used.setdefault(BLOCK_FOR_TERRAIN[t], set()).add(bits)
                if bits == 255:
                    # All four sides the same terrain = interior; pick one of the A/B/C
                    # variants by position hash, so a large area of one material does
                    # not give the copy-paste away
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


# ---------------------------------------------------------------- verification and export

def grid_lua(matrix, title):
    used = {c for row in matrix for c in row if c != '.'}
    unknown = used - set(PAL)
    if unknown:
        raise ValueError(f"characters missing from the palette: {sorted(unknown)}")
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
    """The colours a material **actually emits onto the canvas**, sorted by value from
    dark to light.

    This is what the gate measures, not some hand-written "ramp table" -- the table
    and the code can tell different stories: four tiers declared, one flat colour
    emitted, exactly the dirt/rock case in the previous review, which the declaration
    itself could not reveal.
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
    """Turn "does it look hand-drawn" into assertions that fail.

    Checked one by one against the usual tutorial standards: ramps must shift hue
    (cool dark end, warm light end, >=10 degrees of spread -- raising lightness only
    is a straight ramp), one palette must lend colours to itself (several independent
    ramps in one image fight each other and look like stickers), boundaries must be
    ragged (not all landing on the same straight line), textures must show no obvious
    directionality (strokes must not crowd into one column), recognisable detail must
    remain under the main colour (non-main >=8%, otherwise it is flat fill), and one
    item must not repeat so often that a large area gives the copy-paste away.
    """
    problems = []
    ramps = {}

    for terrain in MATERIALS:
        ramp = emitted(terrain)
        ramps[terrain] = set(ramp)
        if len(ramp) < 3:
            problems.append(f"{terrain} emits only {len(ramp)} tones {ramp}; it reads as one flat colour")
            continue
        hs = [_hsv(PAL[c])[0] for c in ramp]
        spread = max(_hue_arc(hs[0], h) for h in hs[1:])
        if spread < 10:
            problems.append(f"{terrain} ramp changes only value: its emitted {ramp} spans "
                            f"{spread:.0f}° of hue < 10° (a straight ramp)")

    names = list(ramps)
    borrowed = [(a, b, sorted(ramps[a] & ramps[b]))
                for i, a in enumerate(names) for b in names[i + 1:]
                if len(ramps[a] & ramps[b]) >= 2]
    if len(borrowed) < 2:
        problems.append(f"materials do not borrow colour: only {len(borrowed)} pairs share >=2 tones (need >=2 pairs)")

    straight = total = 0
    for bits in CONFIGS:
        if bits & N:
            continue                                # top edge connected: no boundary here
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
        problems.append(f"borders too regular: {ratio:.0%} of boundary columns sit on an un-jittered line (want <=50%)")

    for name, primary in (("grass", 'G'), ("dirt", 'D'), ("sand", 'S'), ("rock", 'R')):
        grid = base_tile(name, 0, 0)
        hist = Counter(c for row in grid for c in row)
        off = [(x, y) for y in range(TILE) for x in range(TILE) if grid[y][x] != primary]
        if not off:
            problems.append(f"{name} is a flat fill: no detail pixels at all")
            continue
        share = len(off) / (TILE * TILE)
        if share < 0.08:
            problems.append(f"{name} lacks detail: non-primary pixels are only {share:.0%} (want 8%-55%)")
        elif share > 0.55:
            problems.append(f"{name} is too busy: non-primary pixels are {share:.0%}, the dominant tone cannot hold it,"
                            f"and it turns into noise when tiled (want 8%-55%)")
        top = hist.most_common(1)[0]
        if top[1] / (TILE * TILE) < 0.45:
            problems.append(f"{name} has no dominant tone: the most common '{top[0]}' covers only "
                            f"{top[1] / (TILE * TILE):.0%} (want >=45%)")
        cols = Counter(x for x, _ in off)
        worst = cols.most_common(1)[0][1] / len(off)
        if worst > 0.5:
            problems.append(f"{name} texture is directional: {worst:.0%} of strokes crowd one column")

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
        problems.append(f"scene repetition: the most repeated tile takes {top[1] / (SCENE_COLS * SCENE_ROWS):.0%}")
    return problems


def selfcheck():
    """Structural checks that run without Aseprite: tile count, geometry, seams,
    phases, palette."""
    problems = []

    if len(set(CONFIGS)) != 47:
        problems.append(f"blob config count {len(set(CONFIGS))} != 47")

    # Both geometric extremes: all-set fills the whole cell; the empty mask is an
    # isolated islet and must not touch the tile border with a single pixel
    if not all(all(mask_for(255)[y]) for y in range(TILE)):
        problems.append("bits=0xFF does not fill 32x32")
    iso = mask_for(0)
    if any(iso[0]) or any(iso[-1]) or any(row[0] or row[-1] for row in iso):
        problems.append("the bits=0x00 island touches the tile border and would join up when tiled")

    # Palette characters must be valid Lua identifiers (paint_grid's data file uses
    # them as keys) and must not be '.'
    bad = [c for c in PAL if not c.isalpha()]
    if bad:
        problems.append(f"invalid palette keys: {bad}")

    # Seam contract: two tiles of the same terrain side by side must have identical
    # coverage pixel by pixel along the **middle** of their shared edge (excluding the
    # two MxM corner regions) -- one pixel off and the map shows a seam running through
    # the terrain's interior.
    # The corner regions at both ends may differ within limits: a blob's corner bit is
    # decided by "the neighbours on either side of that corner", and when a terrain
    # boundary forms a T-junction between two adjacent cells the two tiles do not see
    # the same diagonal cell, so a few pixels of notch are inherent to the 47-blob
    # scheme (Godot / Tiled blobs are the same), not a geometry bug.
    # Threshold 8 = one row of an 8px-wide corner region on a single side; beyond that
    # it really is drawn wrong.
    terr = scene_map()
    worst = 0

    def seam(tag, a_line, b_line):
        nonlocal worst
        # The "middle" must avoid the jitter band: the boundary line itself wanders
        # within MARGIN +/- JITTER, and a one or two pixel difference between the two
        # tiles there is exactly the intent; pixels differing outside the jitter band
        # are a real mistake.
        lo, hi = MARGIN + JITTER, TILE - MARGIN - JITTER
        mid = [i for i in range(TILE) if lo <= i < hi]
        if [a_line[i] for i in mid] != [b_line[i] for i in mid]:
            problems.append(f"{tag} coverage is discontinuous across the middle band")
        worst = max(worst, sum(1 for i in range(TILE)
                               if (i < lo or i >= hi) and a_line[i] != b_line[i]))

    for ty in range(SCENE_ROWS):
        for tx in range(SCENE_COLS - 1):
            if terr[ty][tx] != terr[ty][tx + 1] or terr[ty][tx] == 'grass':
                continue
            a = mask_for(bits_at(terr, tx, ty, SCENE_COLS, SCENE_ROWS))
            b = mask_for(bits_at(terr, tx + 1, ty, SCENE_COLS, SCENE_ROWS))
            seam(f"horizontal seam ({tx},{ty})/({tx + 1},{ty})",
                 [row[-1] for row in a], [row[0] for row in b])
    for ty in range(SCENE_ROWS - 1):
        for tx in range(SCENE_COLS):
            if terr[ty][tx] != terr[ty + 1][tx] or terr[ty][tx] == 'grass':
                continue
            a = mask_for(bits_at(terr, tx, ty, SCENE_COLS, SCENE_ROWS))
            b = mask_for(bits_at(terr, tx, ty + 1, SCENE_COLS, SCENE_ROWS))
            seam(f"vertical seam ({tx},{ty})/({tx},{ty + 1})", a[-1], b[0])
    if worst > 8:
        problems.append(f"corner seam notch too deep: {worst} px at most (threshold 8)")
    selfcheck.worst_corner = worst

    # Every terrain pair that appears in the scene must have a matching transition tile
    for ty in range(SCENE_ROWS):
        for tx in range(SCENE_COLS):
            t = terr[ty][tx]
            for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
                nx, ny = tx + dx, ty + dy
                if not (0 <= nx < SCENE_COLS and 0 <= ny < SCENE_ROWS):
                    continue
                if not adjacency_ok(t, terr[ny][nx]):
                    problems.append(f"({tx},{ty}){t} borders ({nx},{ny}){terr[ny][nx]} "
                                    f"but the atlas has no transition for that pair")

    # Water animation: the 4 frames must be pairwise distinct (or the GIF encoder
    # merges frames)
    hashes = {json.dumps(sheet_frame(p)) for p in range(WATER_PHASES)}
    if len(hashes) != WATER_PHASES:
        problems.append(f"only {len(hashes)}/{WATER_PHASES} water phases differ")

    # Props: non-empty, and the slots must fit
    if len(PROP_NAMES) > (ROWS - PROP_ROWS[0]) * COLS:
        problems.append("more props than the atlas rows can hold")
    for name in PROP_NAMES:
        if all(c == '.' for row in render_prop(name) for c in row):
            problems.append(f"prop {name} is empty")

    seen_props = set()
    for px, py, name in SCENE_PROPS:
        if not (0 <= px < SCENE_COLS and 0 <= py < SCENE_ROWS):
            problems.append(f"prop {name} is placed outside the scene ({px},{py})")
            continue
        if (px, py) in seen_props:
            problems.append(f"two props claim the same cell ({px},{py})")
        seen_props.add((px, py))
        if terr[py][px] not in PROP_TERRAIN_OK[name]:
            problems.append(f"prop {name} sits on {terr[py][px]} at ({px},{py}),"
                            f"only {'/'.join(sorted(PROP_TERRAIN_OK[name]))} is allowed")

    # Looks gate: "does it look hand-drawn" also becomes a failing assertion
    problems += art_audit()
    return problems


def preview_png(path: Path):
    """2x preview for judging the image locally; not a deliverable (Aseprite exports
    the deliverable)."""
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
        raise SystemExit(f"selfcheck: {len(probs)} problem(s)")
    print("selfcheck: green")
    here = Path(__file__).parent / ".build"
    here.mkdir(exist_ok=True)
    print("preview:", preview_png(here / "atlas_preview.png"))
