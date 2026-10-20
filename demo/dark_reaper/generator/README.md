# dark_reaper generator

32x32 dark reaper, 4 directions x 6 frames walk cycle.

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py          # create session -> one atomic batch draws all 24 frames -> per-frame QA -> per-pixel verification -> package
python reaper.py           # does not touch Aseprite, ASCII only
python reaper.py --sheet   # local contact sheet .build/reaper_sheet.png
```

Outputs go to the parent `demo/dark_reaper/`: `dark_reaper_walk_{down,left,right,up}.gif` (4x, 6 frames
each), `dark_reaper_spritesheet.png` (192x128), `dark_reaper_walk.ase` (24 frames + 4 `walk_*` tags).
Intermediate files live in `.build/` (gitignored).

## These 24 frames use only the v2 tool surface

| | Old (when the op registry could not add frames yet) | Now |
| --- | --- | --- |
| Structure | `run_lua` with hand-written Lua: `newFrame` / create empty cels / set duration / `newTag` | `add_frames` + `set_durations` + 4x `add_tag` |
| Pixels | 4616 `draw_rect` ops in 4 batches, `timing_ms` totalling 1332ms | 24 `paint_grid` ops (one per frame), in the same batch as the structure |
| Ops / Aseprite processes for one full draw | 4618 ops / 7 processes (create session, build structure, 4 pixel batches, save) | **31 ops / 1 process**, measured `timing_ms` 371-673ms, zero warnings |

Those 31 ops form one atomic batch: `add_frames{count: 23}` → 24x `paint_grid` →
`set_durations{[0.12] * 24}` → 4x `add_tag` → `save_sprite`.
`add_frames` must come before `paint_grid`: a new document has only 1 frame; the op auto-creates cels,
but it **does not** auto-create frames.

- One Lua grid file per frame (`reaper.py`'s `grid_lua()`; rows are strings, `.` is transparent), written
  into the **session work directory** `<.build>/work/sessions/<session_id>/reaper_NN.lua`, so `paint_grid`
  is exempt from `confirmed=true` — see the gate convention in `AGENTS.md`: a file inside the work
  directory counts as trusted input.
- `run_lua` is left with only the export (`ExportSpriteSheet` + `saveCopyAs`): the tool surface has no
  export op, and this is a legitimate use of the escape hatch. On a multi-frame document
  `saveCopyAs("frame.png")` writes `frame1.png…frame24.png` (it never writes `frame.png`), and those 24
  files are exactly what the per-frame verification consumes.

## QA is metrics, not "no errors reported"

`produce.py` first runs `inspect` frame by frame over all 24 frames (24 headless processes, about 6s
measured — the most expensive stretch of the script; the whole run takes about 20-23s, slower than the
old version's 16.5s, and the slowdown is exactly QA going from "only look at frame 1" to "look at every
frame"), and fails without packaging if any check misses; only then does it compare the exported frames
against the Python-side design grids pixel by pixel (0 differing pixels across 24/24 frames). Each frame
also cross-checks document-level facts: `frames_total == 24` and the tag list == `walk_down/left/right/up`
(`inspect` is read-only, but if it ever modifies the original document, this will fire). The GIF side has
its own assertion: the 6 frames per direction are pairwise different, otherwise the encoder silently
merges identical frames.

The metrics turned up two hard defects on this machine, both fixed back in `reaper.py`'s model:

- **`bbox` bottom edge**: on the first per-frame inspect after the migration, 16 frames read 30 and 8
  frames (frames 5 and 6 of each direction) read **32** — the outline touched the last row of the canvas.
  The bottom edge should be decided by "heel contact + robe hem"; what jumped down was the scythe: the
  shaft is 25/26 rows long, and it pumps ±2px with the gripping hand; at the bottom of the pump the shaft
  base crosses row 28, so it reads as "the scythe is poking the floor" rather than a step. Shortening the
  shaft base by 2 rows (the `shaft` in `scythe()`; blade, gripping hand and pump amplitude untouched by a
  single pixel) makes the bottom edge a constant 30 across 24 frames, with the robe hem sliding between
  24..27 along the wave — that reads as stepping.
- **Red eyes missing from the `palette`**: the `inspect` palette for the 6 right-facing frames had no
  `#FF3B30` (`color_count` 10, versus 12 on the left) — a 2x6 dark patch on the hood's rear edge
  (`rect(21, y+3, 2, 6, "D")`) shares a column with the right-facing eyes and painted the whole pair of
  glowing red eyes over. Swapping those two lines in `hood()` (dark patch first, eyes after) brings the
  red eyes back on the right, `color_count` 10 → 11. On the left the dark patch is behind the head
  (x=9-10) and never competes with the eyes, so this pit only bites on the mirrored side.

The remaining metrics were green from the start, but the assertions stay in the script as guard rails:

- **`isolated_pixels` = 0** (all 24 frames equal): robe, blade and outline are all connected, with no
  noise or broken lines. This is the first check to blow when tattered cloth or ribbons are added later.
- **`near_duplicate_colors` = []**: every pairwise channel difference in the 14-color palette is > 8;
  there are no near colors that ought to be merged.
- **`coverage` 0.50-0.56**: fills the canvas; the robe-hem travelling wave differs by at most 1px between
  columns, with no single column spiking out, so it reads as cloth undulating rather than dissolving.

## How it walks without legs

The reaper is covered by a robe from head to toe, so no leg-step reads; the walk is built from three
things layered together:

- **Robe-hem travelling wave**: the bottom edge of each column is `y = baseline + round(1.0 · sin(0.5x + 2πt))`;
  the time phase advances per frame, so the ripple flows sideways along the robe. The amplitude is held at
  1px and the wavelength widened, so it reads as cloth undulating rather than dissolving.
- **Overall bob** (`bob`): sinks 1px on the contact frame.
- **Bone feet**: two specks of bone color show below the robe, lifting and falling in anti-phase with
  `swing` — the direct cue for "stepping". One foot is always planted on rows 27-28, so the baseline never
  moves; what moves is the robe.

The scythe is another pit: in the front/back views the blade must sweep toward the body's **outside**;
sweeping inward crosses the face and covers the hood. In the side view the blade sweeps forward, laid out
by a parabolic droop plus a taper from shaft to tip, which is more continuous than sampling an arc. All 24
frames were checked pixel by pixel: even the frame where the blade edge comes closest to the eyes (right
view) still has the two shaft columns between them, and the blade never crosses the hood.
