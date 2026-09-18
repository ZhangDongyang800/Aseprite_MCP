# AGENTS.md

MCP server that lets an AI draw pixel art in Aseprite. Python (FastMCP) tools drive `.lua` scripts run inside Aseprite, either as headless CLI subprocesses or over a WebSocket bridge to a live Aseprite window.

## Commands

```bash
pip install -e ".[dev]"      # runtime deps + pytest
python server.py             # start MCP server over stdio
pytest                       # all tests; fast, no Aseprite needed
pytest -m "not e2e"          # skip tests that need real Aseprite
pytest -m e2e                # real Aseprite; auto-skips if not found
pytest tests/test_draw_tools.py::test_draw_pixel -v
```

No linter, formatter, or typechecker is configured — do not invent one.

`ASEPRITE_PATH` defaults to a hardcoded dev-machine path (`src/config.py`, `tests/test_e2e.py`). Set it to run e2e or use the server for real.

## Architecture

```
server.py            create_server(): builds Config/runner/SessionManager, registers every
                     src/tools/*_tools.py + resources + prompts; also starts session cleanup thread
src/config.py        env vars -> Config; scripts_dir is fixed at <root>/scripts (not env-configurable)
src/session.py       SessionManager: work/<uuid>/canvas.ase, expiry
src/runner.py        AsepriteRunner (CLI subprocess) and WebSocketRunner (bridge); identical run_script()
src/bridge.py        WebSocket server in a background thread; tab-delimited text protocol
src/tools/*.py       register_xxx_tools(mcp, session_manager, runner); @mcp.tool functions return dicts
scripts/*.lua        one script per operation; shared helpers in mcp_common.lua
extension/main.lua   Aseprite extension; connects as WebSocket client, dofiles scripts, captures print()
```

- **CLI mode (default, `ASEPRITE_MCP_MODE=cli`)**: one `aseprite -b` process per call. No UI. State persists only via the session `.ase` file.
- **Live mode (`ASEPRITE_MCP_MODE=ws`)**: operates `app.activeSprite` in the running Aseprite. Save is a no-op; callbacks can lag when the window is unfocused.

## Critical gotchas

- **`--script-param` MUST precede `--script`**, or `app.params` is empty. Order is enforced in `AsepriteRunner.run_script`.
- Scripts read `app.params["key"]`; all values are strings. Aseprite Lua has **no `loadstring`**, so params are passed as `key=value`, never Lua literals.
- Every script's first lines must conditionally load `mcp_common.lua` only if `not _G._mcp_common_loaded` (Live mode preloads it, CLI mode does not).
- Use `_mcp_get_sprite(file)`, `_mcp_get_target_image(sprite, layer, frame)`, then `_mcp_maybe_save(sprite, file)`. `layer`/`frame` are **1-based**; missing cels are auto-created.
- `AsepriteRunner` forces `encoding="utf-8"` with a 30s timeout (Windows GBK would otherwise corrupt JSON output).
- Query scripts (`get_*`, `compare_frames`, `run_lua`) print JSON to stdout; Python parses it. Mutation scripts print human-readable text.
- CLI undo is a single-step file copy (`work/<uuid>/undo_backup.ase`); redo only works in Live mode.
- `run_script_with_file()` (`src/tools/utils.py`) auto-injects `file` and optional `layer`/`frame` — use it instead of hand-building params.

## Adding a feature

1. Add `scripts/<name>.lua` following the param/`mcp_common` pattern; reuse `_mcp_pixel`/`_mcp_line`/`_mcp_rect`/`_mcp_ellipse`/`_mcp_fill`/`_mcp_blur`/selection-mask helpers.
2. Register the `@mcp.tool` function in the matching `src/tools/*_tools.py`; call the script whose filename matches the tool name.
3. If you add a new tool module, import it and call `register_xxx_tools(...)` in `server.py:create_server`.
4. Tests mock the runner and capture `@mcp.tool` functions; see `tests/test_draw_tools.py` for the fixture pattern. Script tests assert file existence + the mock call params, not Lua execution.

## References

- `README.md` / `README_CN.md` — user-facing tool catalog, live-mode setup, client config.
- `CLAUDE.md` — deeper architecture notes; its tool counts are outdated, trust the code.
- `docs/` — pixel-art workflow/standards doc (Chinese).
