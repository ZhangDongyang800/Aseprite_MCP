# QA and repair

The loop is **look → measure → classify → repair one variable → look again**. Metrics can pass
on ugly art and fail on intentional style; the image is the primary evidence. The numbers below
were calibrated against the two included examples (16×16 potion, 32×32 8-frame slime) and are
meant to catch the failure modes in [visual-language.md](visual-language.md), not to replace
your eyes.

## 1. Hard gates

A deliverable is not done until all of these are true.

### Canvas and alpha

- Declared canvas size on every frame.
- Transparent background; alpha values exactly `{0, 255}` for pixel art.
- `semi_transparent_pixels == 0` unless the style deliberately uses AA; if so, document it and
  verify the engine/GIF path.
- Content does not touch the canvas edge for icons/characters: **minimum 1 px margin** on all
  four sides. Effects that intentionally bleed are the exception and must be declared.
- No holes inside a solid shape unless they are design holes (handle, eye, mouth).

### Palette and noise

| Asset | Max colours (hard) | Target |
|---|---|---|
| 16×16 icon/item | 12 | 4–10 |
| 32×32 character/enemy | 16 | 6–12 |
| Tileset/scene | 32 (shared) | 12–24 |
| FX | 12 | 3–8 + core |

- `near_duplicate_colors == []` (the metric treats ≤8 per channel as indistinguishable).
- No off-palette colours: every visible colour belongs to the declared palette.
- `isolated_pixels == 0`. A deliberate sparkle/star must be documented in the delivery notes;
  otherwise it is a dirty dot.
- No per-frame palette drift: a palette code may not map to two different hex values.

### Silhouette and composition

- Black-fill/silhouette view is identifiable at 1×.
- One focal point with the strongest contrast; no competing highlight.
- 1× read passes on both dark and light backgrounds.
- Coverage is a warning, not a hard target: typical icons 0.25–0.65, characters 0.15–0.45.
  Outside that range, look for “too small in the frame” or “no negative space”.

### Animation

- Same canvas size for all frames; same palette and outline weight.
- Anchor/baseline: grounded frames share the contact row; airborne frames follow an arc.
- Adjacent frames are not identical. Holds are expressed with duration, not duplicate frames.
- Loop closure is non-zero and comparable to adjacent diffs. `pixelqa.py frames --loop` prints
  the numbers; a loop diff much larger than the adjacent diffs is a pop.
- Opaque mass max/min ≤1.35 for idle/walk; ≤1.6 for squash/stretch actions. Values outside
  these ranges are a prompt to look, not an automatic reject.
- Palette consistency: action-only colours (open mouth, flash) are allowed but must be in the
  declared palette.
- Directional views: if mirrored, alpha masks match exactly; if world-lit, shading may differ
  while the silhouette matches.
- Secondary motion (leaf, cloth, weapon) has a lag/settle pattern, not random jitter.

### Files

- `.ase` source exists, opens, and contains the expected frames/tags/layers.
- PNG: exact width/height, alpha 0/255, no semi-transparency, correct frame.
- GIF: exact frame count, per-frame durations match `meta.frames`, loop flag as intended,
  transparent background, no accidental frame merging.
- Sheet: cell size × columns/rows matches the layout; each cell is pixel-identical to the
  corresponding exported frame; no cell-edge bleed.
- File paths are absolute and outside the session work directory (otherwise `close_session`
  deletes them).

## 2. `pixelqa.py` commands

Run from the repository root:

```bash
# grid sources before touching Aseprite
python skills/aseprite-pixel-art/scripts/pixelqa.py grid \
  skills/aseprite-pixel-art/examples/slime-hop/frames/*.lua \
  --min-margin 1 --loop --max-colors 16

# exported frames: sequence, loop, mass curve
python skills/aseprite-pixel-art/scripts/pixelqa.py frames \
  skills/aseprite-pixel-art/examples/slime-hop/export/frame*.png \
  --min-margin 1 --loop --max-colors 16 --max-mass-ratio 1.6

# GIF: count, durations, transparency, per-frame stats
python skills/aseprite-pixel-art/scripts/pixelqa.py gif \
  skills/aseprite-pixel-art/examples/slime-hop/export/slime_hop.gif \
  --expect-frames 8 --expect-durations 140,100,80,80,110,90,70,130

# sheet: cells match the frame PNGs
python skills/aseprite-pixel-art/scripts/pixelqa.py sheet \
  skills/aseprite-pixel-art/examples/slime-hop/export/slime_hop_sheet.png \
  --cell 32x32 --columns 4 \
  --frames skills/aseprite-pixel-art/examples/slime-hop/export/frame*.png

# visual contact sheet
python skills/aseprite-pixel-art/scripts/pixelqa.py contact \
  skills/aseprite-pixel-art/examples/slime-hop/export/frame*.png \
  --out /tmp/slime_contact.png --scale 8 --bg dark --labels
```

Exit code 1 means a hard gate failed. JSON is printed to stdout; inspect `failures` first, then
the per-file `frames`/`reports`/`cells`. Warnings are included in the reports; with `--strict`
you can promote them, but that is not the default.

## 3. `inspect` metrics: what they mean

- `color_count` / `palette`: colours actually visible in the selected frame. Use this for
  palette QA, not `meta.palette`.
- `near_duplicate_colors`: pairs within 8 per RGB channel. Cut or separate them.
- `bbox`: content bounds of the selected frame. Check margins and baseline.
- `coverage`: visible pixels / canvas area. A weak read, but useful for “floating tiny sprite”
  and “no negative space”.
- `semi_transparent_pixels`: must be 0 for pixel art unless AA is intentional.
- `isolated_pixels`: visible pixels with no orthogonal visible neighbour. Must be 0.
- `frame_diffs`: for `frame > 1`, one real diff against the previous frame (`from`, `to`,
  `changed_pixels`, `bbox`); frame 1 returns `[]`. This is not a full sequence report — use
  `pixelqa.py` for all adjacent diffs and loop closure. `grid_offset` was removed.

`inspect` returns one frame at a time. For a sequence, export frames and use `pixelqa.py`; only
inspect the frames you need to look at (key poses, suspected defects).

## 4. Visual review checklist

Look at the actual rendered frames, not just metrics.

1. **1× on dark**: can you name the asset? Is the focal point obvious?
2. **1× on light**: does the outline/contrast survive?
3. **Silhouette**: fill black; is it still identifiable? Are there tangents or merged masses?
4. **Shape**: are diagonals clean? Are there jaggies, 1-px bumps, or accidental holes?
5. **Value**: three groups? Is the shadow directional, not a pillow? Is there one highlight?
6. **Palette**: any colour you did not choose? Any near-duplicate? Is the most saturated colour
   on the focal point?
7. **Face/identity**: eyes/mouth readable? Any feature drifting between frames?
8. **Animation**: play at real speed and cadence; is the loop seamless? Does the contact foot
   slide? Does the mass curve make sense? Does secondary motion lag/settle?
9. **Set consistency**: same light, palette, outline weight, scale, baseline.
10. **Deliverables**: open the actual PNG/GIF/sheet/`.ase`; do not trust the tool's “ok”.

## 5. Defect → repair matrix

| Observation | Diagnosis | Repair |
|---|---|---|
| Silhouette unreadable in black | too much detail / merged masses | simplify to 2–5 masses; remove accessories; redraw the model |
| Shape looks “mushy” | too many value steps, low contrast between adjacent ramps | cut the ramp; increase value separation; merge near-duplicates |
| Pillow shading | shadow follows outline | pick one light; shade planes; remove rim shadow |
| Plastic | same-hue ramp, uniform specular | hue-shift ramp; one specular; add reflected light only if material needs it |
| Jaggies | uneven diagonal steps | recluster to 45°; fix the row lengths in the grid |
| Isolated dots | typo in grid / stray draw_pixel | remove or connect; check the grid row that produced it |
| Dirty fringe | AA into transparency | remove AA; keep alpha 0/255 |
| Icon too small | too much empty margin | scale the design parameters (not the output) to fill 35–65%; keep 1 px margin |
| Icon touches edge | body placed too large | shift/resize the design; never rely on the engine to clip |
| Animation jitters | parts moved independently | anchor torso/head; use one deformed model; keep face relative |
| Foot slide | contact foot moves horizontally | lock the baseline; move only the free leg |
| Loop pops | last frame doesn't lead to first | match phase; adjust last hold; check loop diff |
| Frame identity morphs | features redrawn per frame | place eyes/mouth relative to the deformed body; keep sizes |
| Mass pulses | each frame normalized independently | normalize the group to one body scale; deform around the anchor |
| Wrong shading on mirrored view | whole frame mirrored with world-fixed light | mirror geometry, re-shade with fixed light |
| Ghost pixels after repaint | `paint_grid` skips `.` and does not clear | `clear_canvas` the target cel first, then repaint |
| GIF looks smeared / frame count wrong | semi-alpha or duplicate frames | export at 1×, check durations/count, use 0/255 alpha |
| Sheet cells bleed | no padding / content touches cell edge | add padding or redesign within the cell; re-export |

## 6. Repair policy

1. **Look before changing.** `inspect` the current frame; do not edit from memory.
2. **Classify the defect**:
   - global (proportions, palette, light, silhouette) → edit the design model, clear the
     affected cels, regenerate;
   - local (1–5 pixels) → `draw_pixel`/`draw_rect`;
   - structural (frame/tag/layer) → fix with the structural ops or a fresh build.
3. **Change one variable per pass.** Re-inspect after each pass; do not stack unverified fixes.
4. **Clear before a full repaint.** Old pixels outside the new grid survive otherwise.
5. **Do not use `undo` as an editing strategy.** CLI undo is single-step and unavailable for
   the first batch. Rebuild from the model instead.
6. **Stop after three failed rounds** on the same defect. Report the symptom, what you tried,
   and the measured evidence; ask for a design decision if the brief is ambiguous.
7. **Never claim success from tool `ok`.** Check the actual files and the rendered image.

## 7. Evidence to record

For a final delivery, write a short manifest:

```json
{
  "asset": "moss slime hop",
  "canvas": [32, 32],
  "palette": ["#1E1A2E", "#24523B", "..."],
  "frames": {"count": 8, "durations_ms": [140, 100, 80, 80, 110, 90, 70, 130], "tag": "hop"},
  "qa": {"semi_transparent": 0, "isolated": 0, "colors": [10, 11],
         "bbox_margin_min": 1, "loop_diff": 98, "mass_ratio": 1.251},
  "files": ["slime_hop.ase", "slime_hop.gif", "slime_hop_sheet.png", "frame1-8.png"]
}
```

The numbers are evidence only if they came from the produced files. Keep the raw JSON output
from `pixelqa.py` next to the deliverable if the project needs an audit trail.
