# slime_devourer generator

A 32x32 action animation of the "slime devourer", 4 directions x 5 frames (idle → windup crouch → lunge
with open maw → chomp → swallow bulge), not hand-drawn: `monster.py` generates the character grids
parametrically from two ellipses (a cranium plus a lower jaw rotating in the opposite direction around a
hinge at the mouth corner), and `produce.py` lands them in Aseprite and runs QA.

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe   # falls back to auto-detection if unset
python demo/slime_devourer/generator/produce.py             # the only entry point: create session -> one batch of ops -> inspect QA -> per-pixel verification -> package
python demo/slime_devourer/generator/produce.py --preview   # only writes the local contact sheet .build/sheet_preview.png, without launching Aseprite
python demo/slime_devourer/generator/monster.py             # prints 20 frames of ASCII, for tuning the shape
```

Intermediate files all live in `.build/` (gitignored): `monster.ase`, `monster_sheet.png`,
`monster_data.json`, `frames/frame_1..20.png`, `sheet_preview.png`; session state lives in `.build/work/`.
Deliverables sit in the parent directory: the four directional GIFs, `slime_devourer_spritesheet.png`,
`slime_devourer_devour.ase`.

## Division of responsibilities

- **One atomic `apply_operations` batch draws the whole monster** (27 ops = one Aseprite process):
  `add_frames` (extend to 20 frames) → 20 `paint_grid` (one per frame) → `set_durations` (five different
  per-frame durations) → 4 `add_tag` (`devour_down/left/right/up`) → `save_sprite`. The document is created
  by a separate `create_sprite` call to obtain the `session_id`, because the grid files must be written
  into the session directory.
- **Grid files are written into `<.build>/work/sessions/<session_id>/monster_NN.lua`** (inside the work
  directory, so `paint_grid` is exempt from `confirmed=true`). The content is a Lua table file rather than
  JSON: on this machine `json.decode` returns userdata, and neither `pairs()` nor `#` works on it, so
  `dofile` is the only route.
- **`inspect` reads back structure and metrics** (the `frame` parameter picks the frame; read-only, never
  modifies the document).
- **`run_lua` is left with only exports**: the sprite sheet via `app.command.ExportSpriteSheet` plus
  per-frame PNGs. Per-frame PNGs require copying each frame into a temporary single-frame document before
  `saveCopyAs` — calling `saveCopyAs("x.png")` directly on a multi-frame document writes `x1.png..xN.png`,
  and the exact filenames are not obtainable.

An earlier version of this file listed two premises that do not hold; they have been removed:

- ~~"the op registry cannot add frames, `frame=2` reports frame index out of bounds, and animation
  structure must go through the escape hatch"~~ the three structural ops `add_frames` /
  `set_durations` / `add_tag` have long been in the registry; the hand-written frame-building Lua is gone.
- ~~"inspect throws FileNotFoundError on multi-frame documents, so structure can only be probed with
  run_lua"~~ `scripts/inspect.lua` now collapses its temporary copy to a single frame before exporting
  the PNG, so multi-frame documents inspect fine.

The pixel side no longer goes through `draw_rect` either: the old version ran one batch per direction,
3248 ops across 4 batches (310/310/306/327ms on this machine, 1253ms in total, plus one structural
`run_lua`); now 27 ops run as one atomic batch, taking 340~420ms on this machine (632ms for the run that
cold-starts a session).

## Shape model

In the side view the mouth is "a notch bitten through the silhouette", not a hole inside the body: the
upper jaw lifts and the lower jaw drops, and the wedge between them is the oral cavity. The geometry emits
semantic masks only; shading and outlines are computed uniformly in the render stage, so `right` is the
horizontal mirror of `left`'s mask while the light stays fixed top-left — mirroring the whole `left` frame
over would differ by 42~68 shading pixels, which is exactly what happens when the light does not flip with
it, not a defect. Reshaping only needs edits to `SIDE_CFG` / `FRONT_CFG` and the mask constructors, then a
rerun of `produce.py`.

## QA (`qa()` in `produce.py`, reading the metrics that inspect hands back)

Packaging only happens when everything is green; any failing check raises `SystemExit(1)` and lists the
defects:

- `isolated_pixels` is 0 on all 20 frames (an isolated pixel on the slime = a dirty dot). The current shape
  has no isolated dots anyway; this is a regression gate: if a future reshape breaks the outline, this
  fails outright.
- `near_duplicate_colors` went from 6 frames reporting `#F4F7E4` (teeth) vs `#F6FFE8` (eye glint) (channel
  differences 2/7/4, all within the threshold of 8) down to 0: the teeth became `#E7EEDA`, R15/G16 away
  from the glint, still in the same cool branch, and the highlight hierarchy (the glint stays brightest)
  is unchanged.
- `semi_transparent_pixels` 0 (`paint_grid` always uses alpha=255, so GIF's 1-bit transparency never gets
  smeared by half-transparent pixels).
- **The bbox must not touch the canvas edge**: the lunge frames of `left`/`right` (8/13) used to have the
  crown outline pressed against row 0, effectively cut off by the canvas; changing `SIDE_CFG[2].lean` from
  `(-3,-1)` to `(-3,0)` (shifting the whole frame down 1px, shape unchanged) now leaves a 1px margin on
  all sides.
- **Volume curve** (bbox size / coverage): the windup squashes, the lunge stretches longest and fullest,
  the chomp contracts, and the swallow pushes the silhouette up; `produce.py` prints a table:

  | Phase | down (front) | left | right | up (back) |
  |---|---|---|---|---|
  | idle | 22x26/0.479 | 23x27/0.504 | 23x27/0.504 | 22x26/0.479 |
  | windup | 24x24/0.479 | 24x26/0.522 | 24x26/0.522 | 24x24/0.496 |
  | lunge | 22x27/0.496 | 23x30/0.557 | 23x30/0.557 | 22x27/0.512 |
  | chomp | 24x25/0.488 | 23x26/0.510 | 23x26/0.510 | 24x25/0.506 |
  | swallow | 22x28/0.496 | 22x28/0.522 | 22x28/0.522 | 22x28/0.496 |

  The back view used to get wider the more the mouth opened (`wide = 1 + 0.055 * mx` with no cap: during
  the lunge the cranium radius went 8.8→12.0 and the silhouette came out 26 wide against 22 in the front
  view — one size fatter at the same instant). It is now capped at "at most 1px more cranium radius than
  the front view", so the front/back silhouettes match exactly at every phase, and switching direction no
  longer suddenly changes body size.
- **Directional consistency**: `right`'s alpha mask must equal the horizontal mirror of `left`'s, the bbox
  sizes must match, and x must satisfy `x_left + x_right + width == 32`.
- **Frame durations differ per frame**: the five phases `[0.2, 0.1, 0.08, 0.09, 0.22]` seconds (on this
  machine `Frame.duration` is interpreted in seconds) are pairwise different; `set_durations` writes all 20 frames in
  one go, and inspect reads them back for a frame-by-frame comparison (±5ms). At packaging time there are
  further assertions that the GIF really carries `[200, 100, 80, 90, 220]` and that the encoder did not
  merge the 5 frames (the five are pairwise different; `n_frames == 5` is the probe for this contract).

Beyond the checks there is one hard gate: `verify()` compares each exported frame PNG against
`monster.py`'s design matrix pixel by pixel; all 20 frames must have 0 differences, and if it is not 0 it
prints the differing pixels and skips packaging.
