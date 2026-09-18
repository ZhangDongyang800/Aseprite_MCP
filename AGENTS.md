# AGENTS.md

MCP server that lets an AI draw pixel art in Aseprite. Python (FastMCP) exposes a three-tool surface backed by an op registry; each op is implemented in `.lua` and run inside Aseprite, either as a headless CLI subprocess or over a WebSocket bridge to a live Aseprite window.

## Commands

```bash
pip install -e ".[dev]"      # runtime deps + pytest
python server.py             # start MCP server over stdio
pytest                       # all tests; fast, no Aseprite needed
pytest -m "not e2e"          # skip tests that need real Aseprite
pytest -m e2e                # real Aseprite; auto-skips if not found
pytest tests/v2/test_apply_tool.py::test_apply_operations_happy_path -v
```

No linter, formatter, or typechecker is configured — do not invent one.

`ASEPRITE_PATH` overrides Aseprite auto-detection (`src/aseprite_locate.py`: env var → `PATH` → common install locations, see `src/config.py`). Set it to run e2e or use the server for real.

## Architecture

```
server.py            create_server(): builds Config/runner/SessionManager, registers the v2
                     three-tool surface + resources + prompts; starts session cleanup thread
src/config.py        env vars -> Config; scripts_dir is fixed at <root>/scripts (not env-configurable)
src/session.py       SessionManager: work/<uuid>/canvas.ase, expiry
src/runner.py        AsepriteRunner (CLI subprocess) and WebSocketRunner (bridge); identical run_script()
src/bridge.py        WebSocket server in a background thread; tab-delimited text protocol
src/v2/registry.py   REGISTRY (OpRegistry): single source of truth — OpSpec = name / category /
                     Pydantic params / lua function / mutating+destructive flags; validate() + catalog()
src/v2/compile.py    ops[] -> one generated Lua program; prints one JSON line after __MCP_JSON__
src/v2/executor.py   Engine: per-session lock, CLI file backup, atomic apply, dry_run, undo/redo
src/v2/result.py     Envelope / OpResult / stable ErrorCode — returned by apply_operations and
                     run_lua; inspect instead returns a fastmcp ToolResult
src/v2/inspect.py    metrics computed from the scale-1 exported PNG (palette, bbox, coverage, ...)
src/v2/tools.py      register_v2_tools(): apply_operations, inspect, run_lua
src/v2/ops/          built-in op definitions: draw_ops.py, session_ops.py (imported by __init__.py)
scripts/ops_*.lua    op implementations grouped by category, named _mcp_op_<name>
scripts/inspect.lua  read-only perception export (works on a temp copy; never modifies the document)
scripts/*.lua        legacy one-script-per-tool files, kept for reference until phase-3 cleanup
extension/main.lua   Aseprite extension; connects as WebSocket client, dofiles scripts, captures print()
```

- **Tool surface**: `apply_operations` (only mutation entry; batches run in one `app.transaction`), `inspect` (read-only preview + metrics), `run_lua` (escape hatch; requires `unsafe=true` + `confirmed=true`). Destructive ops (`clear_canvas`, `close_session`) require `confirmed=true`.
- **Ops**: `create_sprite`, `open_sprite`, `save_sprite`, `close_session`, `draw_pixel`, `draw_rect`, `fill_region`, `clear_canvas` (defined in `src/v2/ops/`).
- **CLI mode (default, `ASEPRITE_MCP_MODE=cli`)**: one `aseprite -b` process per call. No UI. State persists only via the session `.ase` file.
- **Live mode (`ASEPRITE_MCP_MODE=ws`)**: operates `app.activeSprite` in the running Aseprite. Save is a no-op; callbacks can lag when the window is unfocused.

## Critical gotchas

- **`--script-param` MUST precede `--script`**, or `app.params` is empty. Order is enforced in `AsepriteRunner.run_script`; still applies to the legacy scripts and `mcp_run_lua.lua`.
- Scripts read `app.params["key"]`; all values are strings. Aseprite Lua has **no `loadstring`**, so params are passed as `key=value` — v2 instead compiles op params to Lua literals (`src/v2/compile.py`).
- Every script's first lines must conditionally load `mcp_common.lua` only if `not _G._mcp_common_loaded` (Live mode preloads it, CLI mode does not).
- Use `_mcp_get_sprite(file)`, `_mcp_get_target_image(sprite, layer, frame)`, then `_mcp_maybe_save(sprite, file)`. `layer`/`frame` are **1-based**; missing cels are auto-created.
- `apply_operations` validates every op and enforces the confirmation gate **before** creating a session; with no `session_id`, a first `create_sprite`/`open_sprite` auto-creates the session and injects `file`.
- `AsepriteRunner` forces `encoding="utf-8"` with a 30s timeout (Windows GBK would otherwise corrupt JSON output).
- v2 batch output is one JSON line after the `__MCP_JSON__` marker, parsed by `parse_result_stdout` (`src/v2/compile.py`); `inspect.lua` prints its metadata JSON on the last stdout line.
- `run_lua` writes the snippet to `<work>/_run_lua.lua` and runs it under the same per-session lock as `apply_operations`/`inspect` (`Engine.session_lock`).
- CLI undo/redo are single-step file swaps (`work/<uuid>/undo_backup.ase` / `redo_backup.ase`); Live mode uses Aseprite's native history.

## Adding an op

1. Implement `_mcp_op_<name>` in `scripts/ops_<category>.lua` (use the standard conditional `mcp_common.lua` header; reuse `_mcp_pixel`/`_mcp_rect`/`_mcp_fill`/`_mcp_blur`/selection-mask helpers).
2. Define its Pydantic params in `src/v2/ops/<category>_ops.py` and register it with `REGISTRY.register(OpSpec(..., lua="_mcp_op_<name>", mutating=..., destructive=...))`; a new category module must also be imported in `src/v2/ops/__init__.py`.
3. Add tests under `tests/v2/` — registry/compile-level plus tool-level with a mocked runner (see `tests/v2/test_apply_tool.py` for the fixture pattern). Lua is not executed in tests.

## References

- `README.md` / `README_CN.md` — install, client config, Live-mode setup, 3-tool surface, demo.
- `CLAUDE.md` — deeper architecture notes; its tool counts are outdated, trust the code.
- `docs/` — pixel-art workflow/standards doc (Chinese).
