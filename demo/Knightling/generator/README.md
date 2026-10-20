# Knightling generator

32x32 chibi knight, 4 directions x 6 frames walk cycle.

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py          # create session -> one atomic batch (structure + 24 frames) -> inspect QA -> per-frame verification -> package
python knight.py           # ASCII only
python knight.py --sheet   # local contact sheet .build/knight_sheet.png
```

`produce.py` pins the server's work directory to `.build/work` (`ASEPRITE_WORK_DIR`): this path must
be pure ASCII, otherwise Aseprite throws a misleading "lua engine missing"; intermediate files
therefore never land in the repo's `work/` either.

Outputs go to the parent `demo/Knightling/`: `knight_walk_{down,left,right,up}.gif` (4x, 128x128),
`chibi_knight_spritesheet.png` (192x128), `chibi_knight_walk.ase` (24 frames + 4 `walk_*` tags).
Intermediate files live in `.build/` (gitignored).

## How the walk is made

Every part in `knight.py` is a function of the phase `t = i / 6`, sharing three channels:

- `swing = sin(2πt)`: the two legs are anti-phase, positive = this leg is in front; the arms and sword follow in anti-phase.
- `bob = round(|swing|)`: the body sinks 1px on the contact frame and comes back up on the passing frame.
- `sway = round(2·swing)`: the cape and plume swing, with a larger amplitude the closer to the hem.

The swing amplitudes are deliberately exaggerated (legs lift 2px in front view, 4px fore/aft in side view),
because the assets are eventually displayed at 4x, and a 1px motion does not read at that size. The sword
translates as a whole rather than moving only the guard, otherwise the sword would be stretched.

`build(direction, frame)` returns a character grid, and `grid_lua()` serializes it into the Lua data
file that `paint_grid` consumes (`palette` + `rows`, with `.` meaning transparent/skip).

## How it gets drawn into Aseprite

Only the v2 tool surface is used. Structure and pixels are packed into **one** `apply_operations`
atomic batch = one Aseprite process; `create_sprite` has to be a separate single call, because the
grid files must be written into the session directory it allocates:

| Purpose | op | Count |
|---|---|---|
| Create the document | `create_sprite` (a separate single call, to get the session_id) | 1 |
| Extend to 24 frames | `add_frames{count=23, duration=0.12}` | 1 |
| Pixels | `paint_grid{path, frame}`, **one per frame** | 24 |
| Per-frame durations | `set_durations{durations=[0.12 x 24]}` | 1 |
| Animation tags for the four directions | `add_tag{walk_down/left/right/up}` | 4 |
| Save the .ase | `save_sprite` | 1 |
|  | **Total** | **31 ops, one batch ≈0.4s** |

The 24 grid files are written into `<.build>/work/sessions/<session_id>/` — inside the session work
directory, so `paint_grid` is exempt from `confirmed=true`. That leaves `run_lua` with the one thing
the tool surface cannot do: export the sprite sheet (`app.command.ExportSpriteSheet`) and the GIF
source frames (`saveCopyAs` on a multi-frame document writes `frame1.png..frame24.png`, which are
exactly the filenames needed here).

## Art QA (the `quality()` function in produce.py)

`inspect` is called once per frame across the 24 frames to read `metrics`; if any check fails it prints
`FAIL:` and exits non-zero:

- `isolated_pixels == 0`: no isolated pixels (noise / broken outlines).
- `near_duplicate_colors == []`: none of the 11 palette colors is judged by the metric as "visually
  indistinguishable" — the closest pair is bright silver `s` and the highlight `w`, 24/21/16 apart per
  channel, while the metric's threshold is ≤8 per channel — so the palette needs no consolidation.
- The `bbox` bottom edge is always row 28: the foot baseline does not drift across 24 frames; the top
  edge bounces between rows 0/1, which is the contact-frame dip from `bob` — part of the walk itself.
- `coverage`, converted to an opaque-pixel count, matches `knight.py`'s model frame by frame (guarding
  against "the op reported success but the pixels never landed"), and left/right frames at the same
  phase must have exactly equal pixel counts.
- `semi_transparent_pixels == 0`, `color_count <= 11`, 24 frames with identical durations, all 4 tags present.

Defects the metrics surfaced, already fixed (all in `knight.py`'s model; the shapes and colors are unchanged):

1. **Right-facing volume larger than left-facing**: right and left should be mirrored silhouettes, but
   frame 3 measured 401 px vs 408 px. The root cause was that the side-view part x constants were copied
   straight from the left view without mirroring: the leg-swing axis 13 (14 for right), the chest highlight
   18..20 (mirror 19..21), the sword hand 15..17 (mirror 16..18), the helmet body 12..20 (mirror 13..21),
   the plume 15+sw (mirror 14+sw). After fixing each one, all 6 left/right frame pairs have pairwise equal
   pixel counts (428/411/401/400/433/448), and the bbox widths agree too.
2. **The right-facing sight slit was half eaten by the blade**: the slit was drawn at 20..23, while the
   blade occupies 22..23 and is drawn later, leaving the right-facing black slit only 2px wide (4px on the
   left). Moving the slit to 18..21 (the mirror position of 10..13 on the left) makes both directions agree.
3. **The right-facing guard is not centered on the blade**: `x-1 if left else x` made the right-facing guard
   stick out 2px to the right and 0px to the left, so the whole sword visually leaned right. Unifying it to
   `x-1` gives 1px on each side, exactly the mirror of the left view.
4. **Front/back leg group 1px too far right**: the legs sat at 12..15 and 17..20 (group center 16), while
   the torso is 10..21 (center 15.5). Changing to 11..14 and 16..19 puts the leg group, torso, helmet and
   belt on the same center axis.

## The unit of frame duration (this section once had a wrong conclusion)

The inputs of `set_durations` and `add_frames{duration}` are **seconds**, and Aseprite's `Frame.duration`
is **also seconds** on the Lua interface, so the 12-frame loop in the `.ase` plays back normally at
0.12s/frame — this section previously inferred from "Aseprite stores milliseconds internally" that
"the `.ase` plays back almost instantly", which was wrong: internal units are not interface units.

Measured: `0.1 / 0.2 / 0.3` seconds export through `saveCopyAs` to GIF delays of exactly `100 / 200 / 300`
ms, and this is pinned in `tests/v2/test_e2e_v2.py::test_duration_unit_survives_into_an_exported_gif`.
The four `knight_walk_*.gif` files get their 120ms/frame from the packaging script, a separate path from
the `.ase`, and the two agree.
