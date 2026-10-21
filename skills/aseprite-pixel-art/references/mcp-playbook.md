# Aseprite MCP playbook

This file is the execution contract for this skill. Every parameter and behaviour below was
checked against the repository's v2 implementation (`src/v2/`, `scripts/`) and against a live
server. Do not invent ops, parameters, or return fields.

## The three tools

| Tool | Purpose | Required flags |
|---|---|---|
| `apply_operations` | The only mutation entry point. Runs an `ops[]` batch. | — |
| `inspect` | Read-only preview image + metrics for one frame. | `session_id` |
| `run_lua` | Arbitrary Aseprite Lua escape hatch. | `unsafe=true`, `confirmed=true` |

`apply_operations` parameters:

```text
ops: list[dict]           # non-empty; each has {"op": name, ...params}
session_id: str | null    # optional when ops[0] is create_sprite/open_sprite
atomic: bool = true       # rollback the whole batch on failure
dry_run: bool = false     # validate only; no session created, no writes
confirmed: bool = false   # destructive ops, or paint_grid outside the work dir
verbose: bool = false     # full echo / dry-run plan
```

Return envelope:

```json
{
  "ok": true,
  "session_id": "uuid",
  "mode": "cli",
  "op_results": [],
  "artifacts": [],
  "warnings": [],
  "changed": true,
  "undo": {"mode": "file_backup", "available": false},
  "timing_ms": 341,
  "error": null
}
```

On failure `ok=false`, `error.code`, `error.message`, `error.hint`, and `op_index` identify
the failed op. With `atomic=false`, a partial run returns `ok=true` plus a
`partial success: N of M ops...` warning and per-op results; inspect the document before
continuing. `op_results` is pruned by design: a successful op that only echoes the caller's
own params has no entry. Do not treat an empty `op_results` as "nothing ran"; use
`inspect`/`changed`/`artifacts`.

A normal CLI batch may contain the warning
`app.transaction unavailable; CLI atomicity enforced by file snapshot` on builds without a
transaction. It is informational in CLI: the server snapshots the `.ase` and restores it on
failure. In Live mode the same warning means rollback is weaker.

`inspect` returns a FastMCP `ToolResult`:

- `content[0]`: preview image (integer upscale, capped at 2048×2048).
- `structured_content`: `{ok, meta, metrics, warnings?}`.
- `meta`: `width`, `height`, `frame`, `frames_total`, `frames` (all durations in seconds),
  `layers`, `palette` (the sprite palette), `tags`, `view`, `scale`, `scale_clamped`.
- `metrics`: computed from a scale-1 export of the selected frame: `width`, `height`,
  `color_count`, `palette` (colors actually visible), `near_duplicate_colors`, `bbox`,
  `coverage`, `semi_transparent_pixels`, `isolated_pixels`, `frame_diffs`.
- `frame` is 1-based and clamped. `view="silhouette"` paints the copy black; any other
  value gives the composite.
- `frame_diffs` contains one real previous-frame diff when `frame > 1`; frame 1 has no
  previous and returns `[]`. It is **not** a full sequence report. Use
  `scripts/pixelqa.py` on exported frames for every adjacent diff and loop closure.
  `grid_offset` was removed because it never carried a meaningful value.
- `meta.palette` is not the used-color list. In RGB mode it can be `["#000000"]` even when
  the art uses eleven colors. Use `metrics.palette` for what is on the canvas. In indexed
  mode, `meta.palette` is the configured palette and index 0 is transparent.

`run_lua` writes the snippet to `<session>/_run_lua.lua` and dofiles it. It returns
`op_results[0].data.stdout` (a string) and nothing else structured. In CLI the document is
snapshotted before the snippet and restored if it throws. Keep snippets short, idempotent,
and verify with `inspect` afterwards.

## Ops (complete registry)

| Op | Params | Semantics and traps |
|---|---|---|
| `create_sprite` | `width` 1–4096, `height` 1–4096, `color_mode` `rgb\|grayscale\|indexed` | Creates a session canvas and returns `canvas_path`. The server overwrites `file` with the session `.ase`; deliver with `save_sprite(path=...)`. Prefer **rgb**; indexed needs `set_palette` first. |
| `open_sprite` | `path`, optional `file` | Opens an Aseprite-supported file into a new session. Not an “import as layer” op. |
| `save_sprite` | `path` optional | Saves the document. **Always pass an explicit absolute `.ase` path.** Without one it depends on `sprite.filename`; error if none. |
| `close_session` | — | Destructive: deletes the whole session directory. Saved artifacts outside it survive. |
| `add_layer` | `name="Layer"`, `opacity=255` | Appends a new layer at the top of the stack (`#sprite.layers`). Returns its 1-based index and name. |
| `set_layer` | `layer`, optional `name`, `opacity`, `visible` | Changes metadata in place. At least one of name/opacity/visible is required. |
| `delete_layer` | `layer` | Destructive. Refuses to delete the last remaining layer. |
| `set_palette` | `colors`: 1–256 `#RRGGBB` values | Sets the sprite palette. Call before painting an indexed document. Index 0 remains Aseprite's transparent index. |
| `draw_pixel` | `x`, `y`, `color` `#RRGGBB`, `layer=1`, `frame=1` | One pixel. Out-of-canvas coordinates error in Lua. Coordinates are relative to the target cel image. |
| `draw_rect` | `x`, `y`, `width>=1`, `height>=1`, `color`, `filled=false`, `layer`, `frame` | **Outline by default**; `filled=true` for a solid block. Both corners are bounds-checked. |
| `fill_region` | `x`, `y`, `color`, `layer`, `frame` | Flood fill the contiguous same-color region at the seed, bounded by the cel. It is not a shape fill and not a global background fill. |
| `clear_canvas` | `layer` (0 = all layers), `frame` | Destructive (needs `confirmed=true`). `layer=0` clears the frame across every layer; `layer=N` clears only that cel. Other frames keep their pixels. |
| `paint_grid` | `path`, `x=0`, `y=0`, `layer`, `frame` | Paints a Lua grid file. `.` skips (leaves old pixels), alpha is forced to 255, unknown codes and out-of-canvas pixels error. See below. |
| `draw_line` | `x1`, `y1`, `x2`, `y2`, `color`, `layer`, `frame` | Bresenham line. Both endpoints must be inside the cel. |
| `draw_ellipse` | `cx`, `cy`, `rx>=1`, `ry>=1`, `color`, `filled=false`, `layer`, `frame` | Outline or filled ellipse. The whole bounding ellipse must fit the cel. |
| `add_frames` | `count` 1–256, `duration` seconds >0, `duplicate=false` | Adds frames. `duplicate=false` clears the copied cels (blank frames); `true` keeps the previous frame as a starting point. |
| `set_durations` | `durations`: list of seconds, 1–256 entries | Sets the first N frames; entries after the list are unchanged. Max 60 s each. |
| `add_tag` | `name`, `from_frame`, `to_frame` | 1-based inclusive range. Duplicate names error. Endpoints are pinned explicitly on this build. |
| `undo`, `redo` | — | Meta ops. Must be the only op in a batch. CLI uses a single-step file swap; the first batch has no backup. Live uses native history. |
| `export` | `format` `png\|gif\|sheet\|frames`, `output`, `scale=1..64`, `frame`, `tag`, `layout`, `columns`, `padding` | Writes deliverables without changing the document or undo stack. `png` needs `frame` on multi-frame sprites; `tag` is only for gif/sheet/frames; `frame` is only for png. Parent directory must already exist. Every artifact is verified after the run. |

Session details:

- Work root: `ASEPRITE_WORK_DIR` (default `<repo>/work`), sessions in
  `<work>/sessions/<uuid>/canvas.ase`. `create_sprite` and `open_sprite` now return a
  `canvas_path` in their op result, so you can place grids beside the canvas without a
  discovery call. In Live mode the path may be empty if the document has no file.
- Fallback discovery from inside the document:
  `run_lua(... code='print(app.activeSprite.filename)')`.
- `paint_grid` may load any Lua file. A path **outside** the server work directory requires
  `confirmed=true`; a path inside it does not. If you cannot resolve the work directory,
  put grids in your own scratch directory and pass `confirmed=true`.
- Sessions expire after `ASEPRITE_SESSION_TIMEOUT` (default 3600 s). `close_session`
  deletes the directory immediately.

## Grid file format

`paint_grid` calls `dofile(path)` and expects a Lua table:

```lua
return {
  palette = { K = "#1E1A2E", M = "#4FAE68", W = "#FFF6D6" },
  rows = {
    "..KKK..",
    ".KMMMK.",
    "..KKK..",
  },
}
```

Rules:

- One character per pixel; `.` means “skip” (not necessarily erase).
- Every non-`.` character must have a palette entry mapping to `#RRGGBB`.
- Rows may have different lengths; the returned `width` is the length of row 1. Keep them
  equal; `pixelqa.py grid` rejects ragged grids.
- Alpha is always 255. There is no semi-transparency in `paint_grid`.
- JSON is not accepted: this build's `json.decode` returns userdata that `pairs()`/`#`
  cannot walk. Use `dofile`-able Lua.
- `x`/`y` are the top-left offset **inside the target cel image**. Keep 0,0 unless you are
  deliberately stamping a small part.
- `paint_grid` does **not** clear first. Repainting a smaller or changed shape leaves the old
  pixels outside the new grid. Clear the target cel before a full repaint:
  `{"op":"clear_canvas","layer":0,"frame":N}` with `confirmed=true` when the frame has
  multiple layers; `layer=1` clears one cel.

## Verified build recipes

### Build a static sprite in two calls

```json
{"ops":[
  {"op":"create_sprite","width":16,"height":16,"color_mode":"rgb"}
]}
```

Use the returned `session_id`, write the grid, then:

```json
{"session_id":"...","confirmed":true,"ops":[
  {"op":"paint_grid","path":"D:/art/potion.lua"},
  {"op":"save_sprite","path":"D:/art/potion.ase"}
]}
```

`confirmed=true` is only because the grid is outside the server work directory. If the grid
lives inside `<work>/sessions/<id>/`, omit it.

### Build an animation in one atomic batch

Create the session first if you need its directory for the grid files; otherwise create and
paint in the same batch with external grids + `confirmed=true`.

```json
{"session_id":"...","ops":[
  {"op":"add_frames","count":7,"duration":0.1},
  {"op":"paint_grid","path":".../frame_01.lua","frame":1},
  {"op":"paint_grid","path":".../frame_02.lua","frame":2},
  {"op":"set_durations","durations":[0.14,0.10,0.08,0.08,0.11,0.09,0.07,0.13]},
  {"op":"add_tag","name":"hop","from_frame":1,"to_frame":8},
  {"op":"save_sprite","path":"D:/art/slime_hop.ase"}
]}
```

One batch is one Aseprite process and one file snapshot. `add_frames` must precede any
`paint_grid` targeting frames > 1.

### Inspect and export

```json
{"session_id":"...","frame":3,"scale":8}
{"session_id":"...","frame":3,"scale":1,"view":"silhouette"}
```

```json
{"session_id":"...","ops":[
  {"op":"export","format":"frames","output":"D:/out/frame.png"},
  {"op":"export","format":"gif","output":"D:/out/anim.gif","scale":4},
  {"op":"export","format":"sheet","output":"D:/out/sheet.png","layout":"rows","columns":4}
]}
```

`format="frames"` writes `frame1.png`…`frameN.png`. Export is non-mutating, so it does not
occupy undo and does not save the `.ase`. Export in its own batch, after the save, so a later
failure cannot leave an uncommitted artifact.

### Repaint one frame safely

```json
{"session_id":"...","confirmed":true,"ops":[
  {"op":"clear_canvas","layer":1,"frame":5},
  {"op":"paint_grid","path":".../frame_05_v2.lua","frame":5}
]}
```

Clear before the paint in the same batch. If the art is on several layers, clear each layer
that the new grid owns; use `layer=0` to clear the whole frame in one op.

### Local corrections

Use `draw_pixel` for 1–5 pixels, or `draw_rect`/`fill_region` for a solid block/region.
Do not repair a 30-pixel shape error one op at a time; edit the design model, clear the cel,
and repaint the frame. That keeps the source and the deliverable in sync.

## Layers and palette (ops, not `run_lua`)

These are ordinary ops now:

```json
{"session_id":"...","ops":[
  {"op":"add_layer","name":"FX","opacity":180},
  {"op":"set_layer","layer":2,"name":"Effects","visible":true},
  {"op":"set_palette","colors":["#14101E","#D04648","#DAD45E","#5CCBAA"]}
]}
```

- `add_layer` appends at the top of the stack and returns its 1-based index. `paint_grid`
  addresses layers by that index; re-check `inspect.meta.layers` after any structural change.
- `set_layer` requires at least one of `name`, `opacity`, `visible`.
- `delete_layer` is destructive (`confirmed=true`) and refuses to delete the last layer.
- `set_palette` accepts 1–256 `#RRGGBB` values. In RGB mode the palette is project metadata;
  verify pixels with `metrics.palette`. In indexed mode call it **before** painting.

## Colour modes

- **RGB** is the default and the safest path for full-colour art.
- **Indexed** now works with the draw ops: each hex is mapped to the sprite palette (exact
  match when present, nearest colour otherwise). **Index 0 is Aseprite's transparent index**;
  keep it unused and paint with indices 1+. Call `set_palette` before `paint_grid`, and verify
  `metrics.palette` / `color_count`. The mapping is RGB-distance based; near-duplicate palette
  entries are ambiguous, so keep the palette clean.
- **Grayscale** changes how the draw ops interpret colours; do not use it unless the user
  explicitly asks for a grayscale asset and you verify the output.

## `run_lua` fallbacks

Only use these when the op vocabulary genuinely cannot do the job. Both flags are mandatory:

```json
{"session_id":"...","unsafe":true,"confirmed":true,"code":"..."}
```

### Move a cel / offset a whole drawing

```lua
local sp = app.activeSprite
local cel = sp.layers[1]:cel(1)
cel.position = Point(2, -1)
```

Coordinates are cel-image coordinates, so later drawing ops shift with the cel. There is no
region move/flip/rotate op yet; regenerate the grid if the change is larger than a whole-cel
offset.

### Delete frames/tags

`Sprite:deleteFrame` and `Sprite:deleteTag` exist but are not exposed as ops. Prefer
rebuilding the document from the design model; CLI undo is one step and a structural mistake
can require several undos. `delete_layer` **is** exposed (destructive).

## Export metadata

Every export result now includes `frame_count`, `durations` (seconds) and `tags`. A sheet also
returns `columns`, `rows`, `cell_width`, `cell_height`, `from_frame`, `to_frame`, and
`frame_rects` (scaled coordinates). There is still no JSON manifest artifact, trim/extrude,
or per-frame pivot; persist the result fields yourself if the engine needs a manifest file.

## Error and recovery rules

| Symptom | What it means | Action |
|---|---|---|
| `confirmation_required` | Destructive op or external grid without `confirmed=true` | Re-call with `confirmed=true` **only** for the intended op. |
| `unsafe_required` | `run_lua` without `unsafe=true` | Use the op surface first; otherwise pass both flags. |
| `op_failed` + `op_index` | An op failed; atomic batch rolled back | Read `error.message`; fix the op; do not retry unchanged. |
| `partial success: N of M` | `atomic=false` kept earlier ops | Inspect; repair only the missing work. |
| `session_not_found` | Wrong/expired session id | Create a new session; the old files are gone. |
| `no_more_undo` | No CLI snapshot (e.g. first batch) | Reopen/rebuild; do not pretend you undid. |
| `file_error` on export | Parent dir missing / extension mismatch / empty file | Create the parent, match the extension, re-export. |
| Lua error with no stack | Some CLI builds exit `4294967295` silently | Wrap suspicious API calls in `pcall`, bisect; avoid unverified API calls. |

## Resources available in the server

If the client exposes MCP resources, these are read-only conveniences:
`aseprite://tips/...`, `aseprite://standards/...`, `aseprite://palette/presets/...`,
`aseprite://timing/presets/...`, `aseprite://patterns/...`, `aseprite://tileset/templates/...`.
They are basic reference material; this skill's rules take precedence when they differ.
Do not depend on resources existing in a client — the three tools are the portable surface.

For the measured capability gaps behind these rules, read [mcp-gaps.md](mcp-gaps.md).
