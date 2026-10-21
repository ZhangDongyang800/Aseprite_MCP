# MCP capability gaps

Status: **2026-10-21**. This file distinguishes what was fixed in the current server from what
still requires a workaround. The fixes are covered by `tests/v2/test_gap_fixes.py` and
`tests/v2/test_gap_fixes_e2e.py`; the e2e file runs against real Aseprite and auto-skips when
it is absent.

## Fixed in this pass

### Indexed drawing

`paint_grid` and the draw ops used to pass a packed RGBA integer to `image:drawPixel`; in an
indexed image that number was stored as a raw palette index, so the canvas inspected as empty.
The draw layer now maps each hex to the sprite palette (exact match, otherwise nearest RGB)
and passes the resulting index. Verified with a 4×1 indexed sprite: four visible colours at
indices 1–4 were painted and `inspect` returned `color_count=4` with the exact palette.

Caveat: **index 0 is Aseprite's transparent index.** Keep it unused (or transparent) and paint
with indices 1+. The mapping is RGB-distance based, so near-duplicate palette entries are
ambiguous.

### `inspect` placeholder metrics

`grid_offset` was always `{x:0,y:0}` and `frame_diffs` was always `[]`. `grid_offset` was
removed. For `frame > 1`, `inspect` now exports the previous frame at scale 1 and returns a real
`frame_diffs` entry (`from`, `to`, `changed_pixels`, `bbox`). Frame 1 has no previous frame and
returns `[]`.

Still one frame per call; there is no all-frame report or loop-closure value in `inspect`.

### Frame-wide clear

`clear_canvas{layer:0}` now clears the selected frame across every layer without creating
missing cels. `layer=N` retains the old single-cel behaviour. It is still destructive and
requires `confirmed=true`.

### Layers and palette

New ops:
- `add_layer{name,opacity}` — appends at the top; returns the 1-based index.
- `set_layer{layer,name?,opacity?,visible?}` — at least one change is required.
- `delete_layer{layer}` — destructive; refuses to delete the last layer.
- `set_palette{colors:[#RRGGBB,...]}` — sets the sprite palette; call before indexed painting.

`run_lua` is still needed for groups/reordering and other layer features not listed above.

### Drawing primitives

`draw_line` and `draw_ellipse` now exist; both bounds-check their full extent before drawing.
The remaining primitive gap is text, dither patterns, and arbitrary polygons.

### Session/export metadata

- `create_sprite` and `open_sprite` return `canvas_path` (when a file exists), so callers can
  place grids in the session directory without a discovery call. Live documents without a file
  may return no path.
- Every `export` result now includes `frame_count`, `durations` (seconds), and `tags`.
  Sheet exports also return `columns`, `rows`, `cell_width`, `cell_height`, `from_frame`,
  `to_frame`, and `frame_rects` (scaled coordinates).

## Remaining gaps and workarounds

### 1. `inspect` is still one frame per process

A 24-frame character costs 24 tool calls to read metrics. The new previous-frame diff covers
only the adjacent pair ending at the selected frame, not loop closure.

**Workaround:** export `format="frames"` and run
`python scripts/pixelqa.py frames … --loop`, which computes all adjacent and loop diffs from
the shipped PNGs. Use `inspect` only for key poses and visual review.

**Recommendation:** accept a frame list / `sequence=true` and return a compact per-frame table
plus one preview per requested frame.

### 2. No region transforms

There is no op for moving, flipping, rotating, scaling, or copying a rectangular region. A
whole-cel offset can be done with `run_lua` (`cel.position = Point(dx,dy)`), but that shifts the
drawing coordinate system for later ops.

**Workaround:** regenerate the frame from the design model; use whole-cel offsets only for a
single correction, then re-inspect.

**Recommendation:** add `move_region`, `flip_region`, `rotate_region`, and `offset_cel` with
integer coordinates and explicit bounds.

### 3. No reference-image import as a layer

`open_sprite` opens a file into a separate session; there is no “add this PNG as a locked,
semi-transparent reference layer” op or compositing op. This blocks in-Aseprite tracing and
colour matching.

**Workaround:** use your own vision on the reference and encode the palette/silhouette in the
grid model. Do not assume `run_lua` can load arbitrary external images; this build has known
API gaps around image loading.

**Recommendation:** add `import_reference{path,layer_name,opacity}` and a matching removal path.

### 4. Thin drawing vocabulary beyond line/ellipse

There is no text, dither pattern, polygon, or anti-alias op. `fill_region` is a contiguous
flood fill, not a shape fill.

**Workaround:** author whole sprites as grids; use `draw_rect`/`draw_line`/`draw_ellipse` for
blockouts and `fill_region` only with intentional seed semantics.

**Recommendation:** add `draw_text`, `dither`, and a pattern fill; keep them bounds-checked.

### 5. Export has metadata fields, not a manifest file

`export` returns durations/tags/frame rects in the envelope, but writes no JSON artifact. There
is no trim/extrude, per-frame pivot, layer-separated export, or tilemap/autotile metadata.

**Workaround:** derive a manifest from the returned fields and the known cell size; add 1–2 px
atlas padding in the engine if it bleeds; keep the `.ase` as the editable source.

**Recommendation:** add a `metadata` output path (JSON) and `trim`/`extrude` options.

### 6. `save_sprite` without a path is fragile

Without `path`, the op falls back to `sprite.filename` and errors when there is none. A
freshly auto-created session does have a file, but the deliverable location is implicit.

**Workaround:** always pass an explicit absolute `.ase` path.

**Recommendation:** require `path` in CLI mode, or return the resolved fallback path.

### 7. CLI undo remains single-step

CLI undo/redo is a one-step file swap; the first batch has no backup. Headless Aseprite has no
native history. Live mode uses native history but depends on the GUI document.

**Workaround:** make builds idempotent from grid sources; keep the `.ase` and exports; use
`undo` only for one mistaken batch, not as an editing strategy.

**Recommendation:** expose a bounded multi-step snapshot history, or label the single-step
limitation in the tool schema.

### 8. `run_lua` has no structured return

The snippet returns only stdout; data has to be printed and parsed. A Lua error can arrive as a
bare process exit on some builds, with no stack.

**Workaround:** print one compact JSON-ish line, keep snippets small, wrap risky API calls in
`pcall`, and verify the document with `inspect`.

**Recommendation:** support a return table/JSON payload from `run_lua` and surface it in
`op_results`.

### 9. No tilemap/autotile/slice export

There are no tilemap, slice, or autotile ops. Aseprite's tilemap layer type is not reachable
through the registry; Tiled/Unity/Godot import metadata must be built outside.

**Workaround:** use an ordinary grid, export a uniform sheet, and generate the manifest from the
design model. Validate transitions with the same-terrain neighbour rule.

**Recommendation:** add a tilemap metadata export or at least a generic slice/tag manifest.

### 10. Live mode has weaker failure semantics

CLI has a file snapshot. In Live mode a failed batch can keep its changes when Aseprite
transactions are unavailable; `run_lua` has no file snapshot at all. The envelope warning
says so — read it.

**Workaround:** save before risky snippets; keep operations idempotent; in Live mode prefer one
small verified batch at a time.

**Recommendation:** standardize a transaction guarantee (or a per-batch document snapshot) in
Live mode and return a machine-readable rollback status.

### 11. `paint_grid` remains opaque-only

`paint_grid` forces alpha 255 and has no anti-aliasing. A semi-transparent effect requires
`run_lua` and explicit verification. GIF transparency is binary; check the exported file if the
engine expects soft edges.

**Workaround:** use hard alpha 0/255 for game sprites; reserve semi-alpha for effects and verify
the PNG/GIF the engine will actually load.
