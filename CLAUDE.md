# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Aseprite MCP Server — an MCP (Model Context Protocol) server that lets AI create pixel art in Aseprite. It exposes 49 tools via FastMCP, each backed by a Lua script that runs inside Aseprite either through CLI subprocess (`aseprite -b`) or via a WebSocket bridge to a running Aseprite instance.

## Install & Run

```bash
pip install -e .
```

## Run Tests

```bash
# All tests (unit, fast)
pytest

# All tests with verbose output
pytest -v

# Specific test file
pytest tests/test_draw_tools.py -v

# Single test
pytest tests/test_draw_tools.py::test_draw_pixel -v

# Exclude e2e tests (require real Aseprite)
pytest -m "not e2e"

# Run e2e only
pytest -m e2e
```

Tests live in `tests/` and use mock runners (`mock_runner` fixture in `conftest.py`) to avoid requiring Aseprite. Markers: `e2e` for tests requiring a real Aseprite installation.

## Architecture

### Dual-Mode Execution

```
                    ┌─────────────────────┐
                    │    Python MCP Server │ (FastMCP)
                    │      server.py       │
                    └──────┬──────┬────────┘
                           │      │
              CLI mode     │      │  Live/WebSocket mode
              (subprocess) │      │
                           ▼      ▼
                    ┌──────────┬──────────────┐
                    │AsepriteRunner│WebSocketRunner│
                    │  (runner.py)  │  (runner.py)  │
                    └──────┬───────┴──────┬───────┘
                           │              │
                           ▼              ▼ (via bridge.py)
                    aseprite -b        WebSocketBridge
                    --script x.lua     (ws://127.0.0.1:9001)
                           │              │
                           ▼              ▼
                      Lua scripts    extension/main.lua
                      (scripts/)     (inside Aseprite)
```

- **CLI mode** (`ASEPRITE_MCP_MODE=cli`, default): Each tool call spawns `aseprite -b --script-param k=v --script x.lua`. State is passed via `.ase` files in per-session work directories. No UI.
- **Live mode** (`ASEPRITE_MCP_MODE=ws`): Python starts a WebSocket server; the Aseprite extension (`extension/main.lua`) connects as a client. Commands are forwarded over WebSocket, executed in the running Aseprite window. State is persistent, UI is visible.

Both modes use the same Lua scripts via `mcp_common.lua` which provides `_mcp_get_sprite()`, `_mcp_maybe_save()`, and `_mcp_is_live` — each script checks the mode flag to decide whether to use `app.activeSprite` (Live) or `app.open(file)` (CLI) and whether to save after modifying.

### Key Components

| Module | Role |
|---|---|
| `server.py` | Entry point. Creates FastMCP, registers all tools/resources/prompts, starts background session cleanup. |
| `src/config.py` | `Config` dataclass — reads env vars (`ASEPRITE_PATH`, `ASEPRITE_MCP_MODE`, `ASEPRITE_WS_HOST`, etc.) with defaults. |
| `src/session.py` | `SessionManager` — manages per-session work dirs (`work/<uuid>/canvas.ase`), tracks metadata, auto-cleans expired sessions. |
| `src/runner.py` | `AsepriteRunner` (CLI subprocess) and `WebSocketRunner` (WebSocket bridge). Both implement `run_script(script_name, params) -> dict` with identical return format. |
| `src/bridge.py` | `WebSocketBridge` — runs WebSocket server in a background thread, uses `threading.Event` for sync request/response across threads. Text-line protocol: `<id>\t<script_name>\t<params>`. |
| `src/tools/` | Tool modules (13 total), one per domain. Each has `register_xxx_tools(mcp, session_manager, runner)`. |
| `src/tools/utils.py` | Shared helpers: `validate_color()`, `run_script_with_file()` (auto-injects `file`/`layer`/`frame` params), `parse_json_output()`, `backup_ase_file()`/`restore_ase_file()` (CLI undo). |
| `src/tools/selection_tools.py` | **NEW** Selection tools: select_all, deselect, select_by_color, invert_selection, delete_selection. |
| `src/tools/color_adjustment_tools.py` | **NEW** Unified color adjustment: adjust_colors (brightness/contrast/hue/saturation/lightness). |
| `src/tools/filter_tools.py` | **NEW** Blur filter: apply_blur (box blur, radius 1-3). |
| `src/tools/batch_tools.py` | **NEW** batch_edit (multi-op in one call), run_lua (escape hatch), undo, redo. |
| `src/tools/import_tools.py` | **NEW** 混合管线: cleanup_import_image — 清洗 AI 生成图（去 mixels/棋盘格、锁调色板、去噪）并导入图层。 |
| `src/pixel_cleanup.py` | **NEW** 清洗管线引擎（Pillow）: detect_scale / strip_checkerboard / lock_to_palette / quantize_colors / despeckle。 |
| `src/resources.py` | MCP Resources: palette data, timing presets, tileset templates, pixel art tips, standards rules. |
| `src/prompts.py` | MCP Prompts: guided workflows for sprite creation, iteration, animation, multi-layer, tileset. |
| `scripts/*.lua` | Lua scripts (~72 total). Each is standalone; reads `app.params`, calls `mcp_common.lua` for sprite I/O. Animation consistency scripts: `compare_frames.lua` (frame diff), `export_contact_sheet.lua` (sequence overview), `propagate_cels.lua` (static-layer copy), `tween_cel.lua` (position/scale/opacity tween). `mcp_common.lua` now includes shared drawing primitives (`_mcp_pixel`, `_mcp_line`, `_mcp_rect`, `_mcp_ellipse`, `_mcp_fill`, `_mcp_clear_rect`, `_mcp_gradient`, `_mcp_blur`) and selection mask I/O (`_mcp_save_selection`, `_mcp_load_selection`). |
| `extension/` | Aseprite extension for Live mode. `main.lua` opens a WebSocket client, captures `print`, executes scripts via `dofile`, returns captured output. |

### Lua Script Pattern

Every Lua script follows this pattern:
1. Conditionally `dofile` `mcp_common.lua` if not already loaded (Live mode pre-loads it)
2. Read params from `app.params["key"]`
3. Get sprite via `_mcp_get_sprite(file)` — Live uses `app.activeSprite`, CLI uses `app.open(file)`
4. Get target image via `_mcp_get_target_image(sprite, layer_idx, frame_idx)` — auto-creates missing cels
5. Perform pixel operations using Aseprite Lua API
6. Save via `_mcp_maybe_save(sprite, file)` — no-op in Live mode, `sprite:saveAs(file)` in CLI
7. Print result (captured by caller as stdout)

### Tool Registration Pattern

Each `src/tools/xxx_tools.py` module exports `register_xxx_tools(mcp, session_manager, runner)`. Inside, tools are defined as decorated functions (`@mcp.tool`) that:
1. Validate inputs (colors, session_id)
2. Call `run_script_with_file()` or `runner.run_script()` directly
3. Return a dict `{"success": True/False, ...}`

### WebSocket Protocol

Messages are tab-delimited text lines:
- **Request** (Python→Aseprite): `<req_id>\t<script_path>\t<key1=value1>\t<key2=value2>...`
- **Response** (Aseprite→Python): `<req_id>\t<true|false>\t<stdout_escaped>\t<stderr_escaped>`

Special characters in values are escaped (`\` → `\\`, `\t` → `\\t`, `\n` → `\\n`, `=` → `\\=`). The `params_to_lua()` in `bridge.py` and `split_message()` in `main.lua` handle encoding/decoding.

### Session Lifecycle

- Sessions track a UUID, work directory, `.ase` file path, canvas dimensions, and last-activity timestamp.
- A daemon thread in `server.py` cleans up sessions older than `session_timeout` (default 3600s) every 5 minutes.
- `close_session` deletes the work directory and `.ase` file.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ASEPRITE_PATH` | `D:\cxdownload\...\aseprite.exe` | Path to Aseprite executable |
| `ASEPRITE_WORK_DIR` | `./work` | Session temp directory |
| `ASEPRITE_SESSION_TIMEOUT` | `3600` | Session expiry in seconds |
| `ASEPRITE_MCP_MODE` | `cli` | `cli` or `ws` |
| `ASEPRITE_WS_HOST` | `127.0.0.1` | WebSocket server bind address |
| `ASEPRITE_WS_PORT` | `9001` | WebSocket server port |
