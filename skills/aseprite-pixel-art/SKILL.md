---
name: aseprite-pixel-art
description: Create or improve game-ready pixel art and frame animation through the Aseprite MCP server. Use when designing or drawing sprites, characters, enemies, items, icons, weapons, terrain, buildings, effects, UI icons, tilesets, sprite sheets, or animations (idle, walk, run, attack, hit, death, FX), especially when readability at game scale, palette consistency, silhouette quality, or frame-to-frame coherence matter. Also use when auditing or repairing existing pixel art, choosing canvas/palette/outline budgets, planning MCP op batches, or verifying exported PNG/GIF/sheet/.ase files. Trigger words: pixel art, sprite, pixel animation, tileset, sprite sheet, game asset, Aseprite MCP, 像素画, 像素艺术, 精灵, 帧动画, 游戏素材, 瓦片集.
version: "1.1.0"
license: MIT
---

# Aseprite pixel art

This skill turns the Aseprite MCP's three tools into a professional pixel-art production
pipeline. It is a **drawing and QA discipline**, not a prompt collection. The MCP executes;
this skill decides what to draw, how to verify it, and when to stop.

Use it for static assets, animated sprites, tilesets, UI icons, effects, and audits. Do not use
it for vector illustration, high-resolution painting, or 3D. If the task is “generate a
photorealistic image”, this is the wrong tool.

## Non-negotiables

1. **Design before drawing.** Plan the silhouette, palette, canvas, light, layers, and frames
   before the first MCP call. Never freehand random pixels and hope.
2. **Use a grid source.** Full-frame art goes through `paint_grid`; one `draw_pixel` per pixel
   is a token and consistency failure. `draw_pixel` is for 1–5 pixel corrections.
3. **One palette per asset/set.** Lock it before painting. Every colour must earn its place;
   no near-duplicates, no off-palette colours, no accidental semi-transparency.
4. **Silhouette first.** If the black-filled shape does not read at 1×, stop and fix the shape
   before shading.
5. **Inspect after every material change.** Use `inspect` for the current frame, then export
   frames for sequence QA. Metrics are evidence, not a substitute for looking.
6. **Clear before a full repaint.** `paint_grid` skips `.` and leaves old pixels. Clear the
   target cel in the same atomic batch; otherwise ghosts survive.
7. **Set the palette before painting an indexed document.** Draw ops now map each hex to the
   sprite palette; index 0 remains Aseprite's transparent index. Default to RGB; use indexed
   only when the project needs it, call `set_palette` first, and verify `metrics.palette`.
8. **Deliverables are files, not claims.** Save the `.ase`, export the PNG/GIF/sheet, and verify
   the actual outputs. A green envelope is not a finished asset.

## Pick the task path

| Task | Start here | Required references |
|---|---|---|
| New static asset (icon, item, weapon, character, enemy, tile, prop) | Phase 0 → 6 | [visual-language](references/visual-language.md), [asset-profiles](references/asset-profiles.md) |
| New animation (idle, walk, attack, hit, death, FX loop) | Phase 0 → 6 | [animation](references/animation.md), [visual-language](references/visual-language.md) |
| Tileset / sprite sheet | Phase 0 → 6; add the tileset rules | [asset-profiles](references/asset-profiles.md), [qa-and-repair](references/qa-and-repair.md) |
| Repair a specific defect | Phase 4 → 5 | [qa-and-repair](references/qa-and-repair.md), the relevant visual/animation page |
| Audit existing files | Phase 4 → 6 without repainting | [qa-and-repair](references/qa-and-repair.md), [mcp-playbook](references/mcp-playbook.md) |
| Unsure what the MCP can do | Read the playbook first | [mcp-playbook](references/mcp-playbook.md), [mcp-gaps](references/mcp-gaps.md) |

## Phase 0 — Brief and spec

Fill this before touching Aseprite. If the user did not specify a value, choose a defensible
default and state it.

```text
Asset:              what it is and its gameplay job
Canvas:             WxH (one of 16/24/32/48/64 unless there is a reason)
View:               top-down / 3/4 / side / front
Palette:            named hex list, 4–12 colours for characters/icons
Light:              one dominant direction; fixed in world or follows character
Outline:            1 px outer; selective or full; inner line colour
Layers:             Body / Outline / FX / Reference; only if they earn complexity
Animation:          frames, cadence, loop or one-shot, anchor/pivot, tags
Readability test:   what must be identifiable at 1× in the real game context
Delivery:           .ase + PNG/GIF/sheet + manifest
Acceptance:         specific gates from qa-and-repair.md
```

Defaults for a roguelike/top-down game: 32×32 character or 16×16 icon; 3/4 or top-down;
world-fixed light from the upper left; 1 px dark hue-shifted outline; RGB; transparent
background; 8–12 fps for animation; one anchor at the feet/bottom centre.

## Phase 1 — Design model

Create the art as **data** before it becomes pixels. Keep the source in the project, not in the
MCP session directory.

For a small static asset, write a Lua grid directly or generate it from a tiny Python model:

```lua
return {
  palette = { K = "#241A2E", M = "#B93A4A", W = "#FFF1DA" },
  rows = {
    "..KKK..",
    ".KMMMK.",
    ".KMWMK.",
    "..KKK..",
  },
}
```

For a character or animation, use a parametric Python model that outputs one Lua grid per frame.
This is how the included examples are made: masks/geometry → palette → shading → outline →
`paint_grid` source. It keeps the design editable and makes a full-frame repaint cheap.

Model requirements:

- One palette table shared by every frame; no per-frame spontaneous colours.
- One body model deformed by pose parameters (squash/stretch, offsets, leaf/cape lag), not a
  different creature per frame.
- Face features placed relative to the deformed body; they may not drift independently.
- A defined anchor (feet baseline, effect origin) and a frame range/tag.
- Grid rows all the same width; `.` for transparent; every other character in the palette.
- Save the model and the generated grids so the build is reproducible.

## Phase 2 — Offline validation

Validate the source before spending MCP calls:

```bash
python skills/aseprite-pixel-art/scripts/pixelqa.py grid <frames/*.lua> \
  --min-margin 1 --loop --max-colors 16
```

Check: sizes agree, rows are equal length, palette codes are complete, no unused/duplicate
colours, bbox has a margin, no isolated pixels, frame diffs are non-zero, loop closure is
sensible. Fix the model, not the canvas, until this is green.

## Phase 3 — Build through the MCP

The exact contract is in [mcp-playbook.md](references/mcp-playbook.md). The short version:

1. **Create the session** with `create_sprite` (RGB). Keep the returned `session_id`.
2. **Prepare grid files.** If you know the server work directory, put them in
   `<work>/sessions/<id>/`; otherwise use your own scratch directory and pass
   `confirmed=true` to the `paint_grid` batch.
3. **Build in one atomic batch** where practical:
   `add_frames` → `paint_grid` per frame → `set_durations` → `add_tag` → `save_sprite`.
   `add_frames` must precede grids for frames > 1. Create the session separately when you
   need its directory for grids; otherwise `create_sprite` can be the first op of the batch.
4. **Use `dry_run=true`** for a large or risky batch, then run it for real.
5. **Export in a separate batch** after the save: `format="frames"`, `"gif"`, `"sheet"`, or
   `"png"`. Export does not save the `.ase` and does not use undo.

Repainting: clear the target frame first, then repaint the full grid in the same batch.
`clear_canvas{layer: 0}` clears the frame across every layer; `layer: N` clears one cel.

Layers/palette: use `add_layer` / `set_layer` / `delete_layer` and `set_palette` ops (no
`run_lua` needed). New layers are appended at the top; indices are 1-based. Record the layout
from `inspect.meta.layers` and keep it fixed for the build. For indexed documents, call
`set_palette` before the first paint and remember that index 0 is transparent.

## Phase 4 — Look and measure

For each key frame (not necessarily all frames):

```json
{"session_id":"...","frame":1,"scale":8}
{"session_id":"...","frame":1,"scale":1,"view":"silhouette"}
```

Look for silhouette, value structure, clusters, palette, outline continuity, face/identity, and
the actual 1× read. Then export all frames and run the sequence gates:

```bash
python skills/aseprite-pixel-art/scripts/pixelqa.py frames <export/frame*.png> \
  --min-margin 1 --loop --max-colors 16 --max-mass-ratio 1.6
python skills/aseprite-pixel-art/scripts/pixelqa.py gif <export/anim.gif> \
  --expect-frames 8 --expect-durations 140,100,80,80,110,90,70,130
python skills/aseprite-pixel-art/scripts/pixelqa.py sheet <export/sheet.png> \
  --cell 32x32 --columns 4 --frames <export/frame*.png>
```

`inspect` gives one frame at a time. For `frame > 1`, `metrics.frame_diffs` now contains the
real previous-frame diff (frame 1 has no previous); it is not a full sequence report. Use
`pixelqa.py` for every adjacent diff and loop closure. `grid_offset` was removed. See
[mcp-gaps.md](references/mcp-gaps.md).

## Phase 5 — Repair

Classify before editing:

- **Global** (proportions, palette, light, silhouette, identity): edit the design model, clear
  the affected cels, regenerate. Do not patch a broken shape pixel by pixel.
- **Local** (1–5 pixels): `draw_pixel` or a small `draw_rect`. Re-inspect after.
- **Structural** (frames/tags/layers): prefer rebuilding from the model; CLI undo is one step.

Change one variable per pass. After three unsuccessful rounds on the same defect, stop and
report the symptom, attempts, and measurements; ask for a design decision if the brief is
ambiguous.

Use the defect matrix in [qa-and-repair.md](references/qa-and-repair.md) for the common
symptoms (pillow shading, jaggies, halos, foot slide, loop pop, ghost pixels, palette drift).

## Phase 6 — Deliver and verify

1. Save the editable source with an explicit absolute `.ase` path.
2. Export the deliverables to an absolute directory that already exists. Keep them outside the
   session work directory; `close_session` deletes the session.
3. Verify the actual files: PNG dimensions/alpha, GIF frame count/durations/loop, sheet cells
   pixel-identical to the frame PNGs, `.ase` present.
4. Write a short manifest (canvas, palette, frame durations, tags, QA numbers, file list).
5. Only close the session after every deliverable is saved and verified. `close_session` is
   destructive and requires `confirmed=true`.

## Tool selection matrix

| Need | Use | Avoid |
|---|---|---|
| Whole sprite/frame | `paint_grid` | hundreds of `draw_pixel` ops |
| 1–5 pixel fix | `draw_pixel` | full repaint for a typo |
| Solid block/background | `draw_rect filled=true` | `fill_region` on a blank canvas |
| Fill an enclosed same-colour region | `fill_region` | assuming it is a shape fill |
| Frames, durations, tags | `add_frames`, `set_durations`, `add_tag` | one-frame-at-a-time loops |
| Clear a frame/layer before repaint | `clear_canvas` + `paint_grid` | repainting without clearing |
| Layers/palette | `add_layer`, `set_layer`, `delete_layer`, `set_palette` | inventing op names |
| Lines/ellipses | `draw_line`, `draw_ellipse` | approximating with hundreds of pixels |
| Sequence diffs / loop QA | export frames + `pixelqa.py` | relying on one-frame `inspect.metrics.frame_diffs` |
| Deliverables | `export` | `run_lua` + `saveCopyAs` unless custom naming is required |
| Undo | single-op `undo` batch | relying on multi-step CLI history |

## Asset budgets (starting points)

| Asset | Canvas | Colours | Frames |
|---|---|---|---|
| Icon/item | 16×16, 24/32 if complex | 4–12 | 1 |
| Character | 32×32 or 48×48 | 6–12 | idle 2–4, walk 4–6, attack 3–5 |
| Enemy | 16/32/48 | 5–12 | 2–6 per action |
| Weapon | 24×32/32×32 | 4–10 | 1 (+ glint 1–2) |
| Terrain tile | 16/16 or 32/32 | shared 12–24 | water 4–8 |
| FX | 8–32 | 3–8 + core | 3–6 |
| UI icon | 16/24 | 3–8 | 1–2 |
| Boss | 48–96 | 10–20 | 6–10 per action |

Per-type composition, material, and game-readability rules are in
[asset-profiles.md](references/asset-profiles.md).

## Hard gates (must pass)

- Canvas size exact on every frame; alpha only `{0,255}`; `semi_transparent_pixels=0`.
- 1 px transparent margin for icons/characters; no accidental edge clipping.
- `isolated_pixels=0`; no `near_duplicate_colors`; colour count within the profile budget.
- Silhouette identifiable at 1× on dark and light backgrounds.
- Animation: baseline/anchor stable; no duplicate adjacent frames; loop closure sensible;
  palette consistent; mass curve within 1.35 (idle/walk) or 1.6 (squash/stretch).
- GIF frame count/durations match the document; sheet cells match the exported frames.
- Actual PNG/GIF/sheet/.ase files exist and open; paths are outside the session work directory.

Full thresholds, metric meanings, and repair routing: [qa-and-repair.md](references/qa-and-repair.md).

## Failure examples (from the validation runs)

- **Apex clipped at y=0.** The first slime build had the leaf outline on the top row; `inspect`
  reported `bbox.y=0`. The fix was to lower the apex pose by 1 px and re-run the model, not to
  paint over the edge. Always check bbox margins on every frame.
- **Repaint ghosts.** `paint_grid` skips `.`; changing a frame's silhouette leaves old pixels
  unless `clear_canvas` runs first. The fix is a clear + repaint in one atomic batch.
- **Indexed mode now maps through the palette.** The old build wrote packed RGBA as indices and
  inspected blank. The fix maps each hex to the sprite palette; index 0 stays transparent, so
  keep a transparent entry at index 0 and paint with indices 1+. Call `set_palette` before
  `paint_grid` and verify `metrics.palette`.
- **A red oval mouth read as a nose.** The open-mouth shape was a rectangle; enlarging it to a
  5×4 rounded cavity with a tongue/fang made it read as a mouth at 1×. Shape language beats
  colour detail.

## If the MCP is unavailable or lacks a capability

Do not simulate tool calls or invent ops. Read [mcp-playbook.md](references/mcp-playbook.md) for
the real surface and [mcp-gaps.md](references/mcp-gaps.md) for measured gaps. If a required
capability is missing, say so, propose the closest workaround (usually a design-model change),
and never claim a file or animation exists without verifying it.

## Examples

Both examples are real, reproducible, and pass the gates in this skill:

- [Potion icon](examples/potion-icon/README.md) — 16×16, 11 colours, 1 px margin, hand-authored
  grid; demonstrates the static pipeline and light/palette discipline.
- [Moss slime hop](examples/slime-hop/README.md) — 32×32, 8 frames, durations/tag, squash and
  stretch, secondary leaf motion, loop QA; demonstrates the animation pipeline.

Run their builders from the repository root (they start their own MCP server and write only
inside the example's `.build/` plus the delivered files):

```bash
python skills/aseprite-pixel-art/examples/potion-icon/build.py
python skills/aseprite-pixel-art/examples/slime-hop/build.py
```
