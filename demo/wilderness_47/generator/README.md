# Wilderness 47-blob tileset generator

32x32 tiles in a 12-column x 19-row atlas (384x608, 228 slots); four overlay terrains each with a
**complete** 47-tile blob transition matrix; a 4-frame water loop; plus a 24x16-tile (768x512) example
scene.

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py     # create session -> one batch of ops draws everything -> structure + craft gates + per-pixel verification -> package
python tiles.py       # no Aseprite: runs both gate suites and writes the local preview
```

Outputs go to the parent `demo/wilderness_47/`:

| File | Description |
| --- | --- |
| `wilderness_tileset.png` | 384x608 atlas, first frame (water phase 0) |
| `wilderness_preview.png` | 2x + separators + each cell labelled "slot index block name bitmask", for humans |
| `wilderness_scene.png` | 768x512 scene, exported at 2x for viewing |
| `wilderness_water.gif` | water interior tile at 4x, 4-frame loop |
| `wilderness_manifest.json` | slot index -> row/column / block / bitmask / variant / animated + palette |
| `wilderness_tileset.ase` | 4 frames + the `water_loop` tag (`*.ase` is in .gitignore, generated locally) |
| `wilderness_scene.ase` | single-frame scene document (likewise, not committed) |

Intermediate files live in `.build/` (gitignored).

## Where the number 47 comes from

A tile has 4 edges (N/E/S/W) and 4 corners (NE/SE/SW/NW), 8 neighbour bits in total.
**A corner bit only has visual meaning when both adjacent edges are set** — otherwise it draws exactly the
same as "that corner not set". The legal corner subsets allowed by each of the 16 edge combinations
therefore add up to exactly 47:

```
0 edges 1 + 1 edge 4 + 2 adjacent edges 8 + 2 opposite edges 2 + 3 edges 16 + 4 edges 16 = 47
```

`blob_configs()` enumerates these 47 bitmasks, and `mask_for()` rasterizes them. The bitmask convention
(`bit0=N bit1=E bit2=S bit3=W bit4=NE bit5=SE bit6=SW bit7=NW`) is written into
`wilderness_manifest.json` together with the slot indices;
**the importing engine treats the manifest as authoritative — do not guess from visual order**.

## The geometry must be subtractive

`mask_for()` starts from "the whole tile is overlay terrain", carves a **full-length** base band of width
`MARGIN` along every **unset** edge, then tidies each corner (square / concave arc / nothing / round the
square corner inward).

This rule was forced by the seam check. Both earlier versions worked **additively** from a centre square:

- a corner cell was filled only when "both edges and the corner are set" -> a straight edge spanning left
  to right kept a corner notch at each end, so a row of tiles read as **crenellations**;
- changing it so "a single edge also fills the corner cell" -> the overlay region reached the tile edge at
  the corner while the neighbour had base terrain there, so the border became a string of semicircles and
  the whole terrain read as **clouds**.

Only subtraction lets "the straight edge of continuous terrain" close into one full-length line. `MARGIN`
is the corner arc radius: at 8 (a quarter of the tile) the pond looks like flower petals, and 6 is what
leaves just a "rounded corner" feel.

## Layering and adjacency: the scene can only draw what the atlas supports

`COVERS = {'sand': {'water'}}` and `BASE_OF = {dirt/sand/rock: grass, water: sand}` define the **only**
adjacency relations this atlas supports. The scene does not hand-place tiles: draw a terrain map first,
then lay tiles by looking up the mask from the 8 neighbours via `bits_at()` — a missing tile, or a pair of
adjacent terrains with no transition tile in the atlas, surfaces on the spot. Water is painted over sand,
so sand's blob is not cut off by the water beside it (it is still sand under the water). Props have their
own `PROP_TERRAIN_OK`: reeds only on sand banks, lily pads only on water, trees cannot grow in the river.

## Materials and borders: what makes it look hand-drawn

The first version got the structure right but **did not look good**. An adversarial review measured the
root causes, all in the art language: ramps changed value only (straight ramps), the five materials
borrowed no color from one another, 89% of borders were zero-jitter straight lines, the strokes all
crowded into the same column, and the dirt road's non-dominant color made up only 1.5% (nearly flat fill).
What it does now:

- **One palette that borrows across ramps (34 colors)**. Every ramp shifts both value and hue: the dark
  end leans blue-purple, the light end leans yellow-orange. The cold purple `z` is the dark-end transition
  for dirt, sand and stone alike; the warm beige `y` is the lit top face for both sand and dirt;
  `H`/`h`/`G`/`g` serve both as big grass and as the grass blades poking in at the road edge — borrowing
  makes the five terrains look like one family rather than five stickers.
- **Large color fields use "variable-radius clumps", not value noise**. On a lattice, value noise can only
  paint **axis-aligned rectangles**; tier it and the road comes out as a checkerboard. `_blob_field`
  scatters a few clump centres with different radii, and each pixel takes the value "distance to the
  nearest centre minus that circle's radius", so clumps come in different sizes and swallow one another;
  distances are computed modulo the tile, so they wrap naturally at the border and tile seamlessly. Too
  dense a centre grid (3x3) reads as leopard print again — it is fixed at 2x2 large clumps, and
  small-scale detail is left to `_clump`'s 2-3 pixel strokes.
- **Tier by quantiles, not magic thresholds**. The same hand-tuned thresholds differ wildly across seeds
  (the dirt field's noise measured only 0.36-0.59), so fixed thresholds would put 98% of a material into
  one tier. `_cuts_for` cuts at quantiles of that material's own field, so "the dominant color is thick"
  is a chosen ratio rather than luck.
- **Pull a layer of dominant-color edge around color-patch boundaries** (`eps` in `_soft_tier`). In a
  continuous field the pixels nearest the threshold are exactly the patch contour; painting them in the
  dominant color draws a 1-2px transition band around each clump — that is the "thin transition color",
  and the difference between a hard cut edge and one that looks "painted over".
- **Borders must be ragged but must still line up**. `MARGIN` is the corner arc radius (8 turns the pond
  into flower petals, 6 is right), and the border line itself drifts ±2px via `_smooth1d`; the jitter
  curve is **seeded by which edge it is, not by the bitmask**, otherwise two adjacent tiles each jitter
  their own way and the layout breaks at the seam.
- **The two sides of a border intrude on each other**: grass blades poke 2 cells into the dirt road and
  grit spills outside the road edge, at frequencies 1/9 and 1/7. The first version used 1/4, which reads
  as "the border is dirty" rather than "the border is organic".
- **Water depth is tiered only by distance from shore, and the far tier must be pixel-identical to the interior tile**,
  otherwise a hard line unrelated to the terrain runs across the boundary between shore tiles and interior
  tiles; the dark color is used only for the dark line under wave crests. The horizontal period of the foam
  line, the ripples and the wavelength must all divide the tile width.
- **Stone paving reads through brick seams, not noise**: 16x8 bricks with the seam lines themselves
  drifting are what make it read as "laid block by block". **Interior must have multiple variants**:
  cells surrounded by the same terrain on all four sides pick between A/B/C by a position hash.

## Verification is not "no errors reported"

`tiles.selfcheck()` (does not start Aseprite) + `produce.verify()` (compares against what Aseprite wrote to
disk). Besides the structural criteria there is a set of **craft gates** in `tiles.art_audit()` — it
measures the **colors a tile actually puts on the canvas**, not any hand-written "ramp table" (a table and
the code can tell different stories: four tiers declared while a flat fill comes out, which is exactly what
the first version failed to see):

1. The 47 masks are unique and complete; `0xFF` fills the whole tile, `0x00` is an isolated island that
   must not touch the tile border by a single pixel;
2. **Seam contract**: two same-terrain neighbours must have identical per-pixel coverage over the **middle**
   of their shared border (avoiding the jitter band); the corner zone tolerates a limited notch — when a
   terrain border forms a T-junction between two adjacent cells, the two tiles see different diagonal
   cells, and a notch of a few pixels is inherent to the 47-blob approximation (Godot / Tiled blobs behave
   the same way); more than 8px fails. The current measured maximum is **2** pixels;
3. every pair of adjacent terrains that appears in the scene must have a corresponding transition tile;
   props may only sit on the terrains they allow;
4. **Every ramp's actual on-canvas hue span is ≥10°**;
5. **At least 2 pairs of materials share ≥2 color tiers**;
6. **Zero-jitter border columns ≤50%**, and
   **no more than 50% of strokes may crowd into the same column**;
7. **Non-dominant-color pixels 8%-55%, and the largest single tier ≥45%**: the lower bound guards against
   flat fill, the upper bound against speckle noise — both were left behind after hitting the two extremes
   one after the other in the same round;
8. the most repeated tile in the scene ≤25%; the 4 water phases are pairwise different (otherwise the GIF
   encoder merges frames and the loop is left with one frame);
9. palette keys must be valid Lua identifiers (`paint_grid`'s data file uses them as table keys);
10. the 4-frame atlas Aseprite exports + the scene differ from the design matrices by **0 pixels**.

`python tiles.py` exits non-zero if any metric fails; `produce.py` also runs the same suite at the start.

## What tool surface was used to draw this

- The atlas = **one atomic `apply_operations` batch, 8 ops**: `add_frames` + 4x`paint_grid` (one per water
  phase, ~930k pixels in total) + `set_durations` + `add_tag` + `save_sprite`, measured 1074ms with zero
  warnings; the scene = another batch of `paint_grid` + `save_sprite`, 602ms.
- Grid files are written into the **session work directory**, so `paint_grid` is exempt from
  `confirmed=true` (see the gate convention in `AGENTS.md`: a file inside the work directory counts as
  trusted input).
- `run_lua` is used only to export PNGs — the tool surface has no export op. On a multi-frame document
  `saveCopyAs` writes `x1.png…xN.png`, so it follows `inspect.lua`'s old approach: copy a temporary
  single-frame document, then export.
- Frame duration unit: both op params and `Frame.duration` are **seconds**; do not "casually multiply by
  1000" in Lua.
