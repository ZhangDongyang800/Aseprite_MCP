<div align="center">

# 🎨 Aseprite MCP Server

**Let AI draw pixel art in Aseprite**

A Model Context Protocol (MCP) server that enables AI to create pixel art in Aseprite through pixel-level drawing primitives, read canvas screenshots, and iterate until satisfied.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0%2B-FF6B35?style=flat-square)](https://github.com/jlowin/fastmcp)
[![Aseprite](https://img.shields.io/badge/Aseprite-v1.3%2B-7D9F37?style=flat-square)](https://aseprite.org/)
[![Stars](https://img.shields.io/github/stars/ZhangDongyang800/Aseprite_MCP?style=flat-square&logo=github&color=yellow)](https://github.com/ZhangDongyang800/Aseprite_MCP/stargazers)

<p align="center">
  <a href="README_CN.md">🇨🇳 简体中文</a>
</p>

</div>

<br>

##  Demo

All three characters were drawn by an AI through this MCP — every pixel written by
`apply_operations`, with `run_lua` used only for the structural work the op registry has no op
for (adding frames, setting durations, creating tags, exporting the sheet).

| Character | ↓ Down | ↑ Up | ← Left | → Right | Sprite Sheet |
|:--|:--:|:--:|:--:|:--:|:--:|
| **Chibi Knight**<br>4 dirs × 6 frames | ![](demo/Knightling/knight_walk_down.gif) | ![](demo/Knightling/knight_walk_up.gif) | ![](demo/Knightling/knight_walk_left.gif) | ![](demo/Knightling/knight_walk_right.gif) | ![](demo/Knightling/chibi_knight_spritesheet.png) |
| **Dark Reaper**<br>4 dirs × 6 frames | ![](demo/dark_reaper/dark_reaper_walk_down.gif) | ![](demo/dark_reaper/dark_reaper_walk_up.gif) | ![](demo/dark_reaper/dark_reaper_walk_left.gif) | ![](demo/dark_reaper/dark_reaper_walk_right.gif) | ![](demo/dark_reaper/dark_reaper_spritesheet.png) |
| **Slime Devourer**<br>4 dirs × 5 action frames | ![](demo/slime_devourer/slime_devourer_devour_down.gif) | ![](demo/slime_devourer/slime_devourer_devour_up.gif) | ![](demo/slime_devourer/slime_devourer_devour_left.gif) | ![](demo/slime_devourer/slime_devourer_devour_right.gif) | ![](demo/slime_devourer/slime_devourer_spritesheet.png) |

> The first two are **walk cycles** (the knight steps on anti-phase leg swings; the reaper has no
> legs, so the walk reads through a travelling wave in the robe hem plus alternating bone feet).
> The third is an **action animation**: idle → crouch → lunge with open maw → chomp → swallow,
> with per-phase frame durations.
> Each character ships a re-runnable parametric generator and a per-frame pixel check under
> `demo/<name>/generator/`.

---

> [!IMPORTANT]
> This project requires a local installation of [Aseprite](https://aseprite.org/) v1.3+. AI performs drawing via the MCP protocol by calling the Aseprite CLI + Lua scripts.
>
> Two execution modes are supported:
> - **CLI mode** (default): Each tool call spawns a headless Aseprite process (`aseprite -b`). No UI, state passed via `.ase` files.
> - **Live mode** (WebSocket): AI operates the running Aseprite instance directly through a WebSocket bridge. UI is visible, state is persistent, and you can watch AI draw in real time. See [Live Mode Setup](#-live-mode-optional-websocket) below.


---

##  Table of Contents

- [ Demo](#-demo)
- [ How to Use](#-how-to-use)
- [ Live Mode (Optional, WebSocket)](#-live-mode-optional-websocket)
- [Tools](#tools)
- [ Example Prompts](#-example-prompts)
- [ Contributing](#-contributing)
- [ License](#-license)

---

##  How to Use

### 1. Environment Setup

Before configuring MCP, prepare your local development environment:

| Dependency | Version | Download |
|------------|---------|----------|
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) |
| Aseprite | v1.3+ | [aseprite.org](https://aseprite.org/) (remember the install path) |

### 2. MCP Server Setup

```bash
git clone https://github.com/ZhangDongyang800/Aseprite_MCP.git
cd Aseprite_MCP
pip install -e .
```

This installs `fastmcp` and `websockets` (the latter is required for optional [Live Mode](#-live-mode-optional-websocket)).

### 3. Client Configuration

> [!IMPORTANT]
> Replace the paths below with your actual local paths:
> - Path to `server.py` in `args`
> - `ASEPRITE_PATH` environment variable value
> - `python` path in `command`

**TRAE:**

Open TRAE → Settings → MCP → Add MCP Server, paste:

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "python",
      "args": ["C:\\path\\to\\Aseprite_MCP\\server.py"],
      "env": {
        "ASEPRITE_PATH": "C:\\Program Files\\Aseprite\\aseprite.exe"
      }
    }
  }
}
```

**Codex CLI:**

Config file: `~/.codex/config.toml`

```toml
[mcp_servers.aseprite]
command = "python"
args = ["/path/to/Aseprite_MCP/server.py"]

[mcp_servers.aseprite.env]
ASEPRITE_PATH = "C:\\Program Files\\Aseprite\\aseprite.exe"
```

After configuration, ask your AI tool to use Aseprite-related tools to start creating.

---

## 🎥 Live Mode (Optional, WebSocket)

Live mode lets AI operate your **running Aseprite instance** directly — you can watch every stroke happen in real time on your screen, and the sprite state persists across tool calls (no repeated file open/save overhead).

### How It Works

```
┌─────────┐    MCP (stdio)    ┌──────────────┐   WebSocket    ┌──────────────────┐
│  AI/TRAE │ ───────────────► │ Python MCP   │ ─────────────► │ Aseprite Extension│
│          │ ◄─────────────── │ Server       │ ◄──────────── │ (WebSocket client) │
└─────────┘                   └──────────────┘                └──────┬───────────┘
                                                                     │ Lua app.* API
                                                                     ▼
                                                              ┌──────────────┐
                                                              │ Visible Aseprite │
                                                              │ Sprite + UI      │
                                                              └──────────────┘
```

The Python MCP server starts a WebSocket server on `127.0.0.1:9001`. The Aseprite extension connects to it as a client. Each MCP tool call is forwarded to Aseprite over WebSocket, executed via the existing Lua scripts, and the result is sent back.

### Setup

**1. Install the Aseprite extension**

The extension is in the `extension/` folder of this repo. Install it via:

- Open Aseprite → `File > Scripts > Open Scripts Folder`
- Copy the entire `extension/` folder contents into the scripts folder (or use `Edit > Preferences > Extensions > Add Extension` and select the `extension/` folder)

**2. Enable WebSocket mode in MCP config**

Add `ASEPRITE_MCP_MODE=ws` to the `env` section of your MCP server config:

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "python",
      "args": ["C:\\path\\to\\Aseprite_MCP\\server.py"],
      "env": {
        "ASEPRITE_PATH": "C:\\Program Files\\Aseprite\\aseprite.exe",
        "ASEPRITE_MCP_MODE": "ws",
        "ASEPRITE_WS_HOST": "127.0.0.1",
        "ASEPRITE_WS_PORT": "9001"
      }
    }
  }
}
```

**3. Connect Aseprite**

With the MCP server running, open Aseprite and click:

`File > Scripts > MCP Bridge: Toggle Connection`

You should see an alert: "MCP Bridge: Connected to ws://127.0.0.1:9001".

Now AI can operate Aseprite directly — create a sprite, draw pixels, and you'll see it happen live.

### CLI vs Live Mode Comparison

| Aspect | CLI Mode (default) | Live Mode (WebSocket) |
|--------|-------------------|----------------------|
| UI visibility | Headless (`-b` flag) | Full UI, watch AI draw |
| State persistence | Per-call (file-based) | Persistent across calls |
| Startup overhead | New process per call | Single running instance |
| Setup complexity | None | Install extension + connect |
| Aseprite focus required | No | Yes (callbacks delayed when unfocused) |
| Fallback | N/A | Auto-falls back to CLI if extension not connected |

> [!TIP]
> If the Aseprite extension is not connected, Live mode tools return a clear error message guiding you to connect. The existing CLI mode is always available as fallback by setting `ASEPRITE_MCP_MODE=cli` (or removing the variable).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASEPRITE_PATH` | auto-detected | Path to the Aseprite executable (overrides auto-detection via `PATH` and common install locations) |
| `ASEPRITE_MCP_MODE` | `cli` | Execution mode: `cli` or `ws` |
| `ASEPRITE_WS_HOST` | `127.0.0.1` | WebSocket server bind address |
| `ASEPRITE_WS_PORT` | `9001` | WebSocket server port |

---

## Tools

Exactly three MCP tools:

| Tool | Description |
|------|-------------|
| `apply_operations` | Execute a batch of ops inside one transaction — the only mutation entry point. Pass `session_id` + `ops[]`; `dry_run=true` validates without side effects; `confirmed=true` is required when the batch contains a destructive op (`clear_canvas`, `close_session`). If `session_id` is omitted and the first op is `create_sprite` / `open_sprite`, a session is created automatically. |
| `inspect` | Read-only perception: returns a canvas preview image plus quantitative metrics (palette, color count, bounding box, coverage, semi-transparent and isolated pixels). On animated documents, `frame=N` steps through frames one at a time. Never modifies the document. |
| `run_lua` | Escape hatch: run arbitrary Lua. Requires `unsafe=true` and `confirmed=true`. |

Ops are named operations registered in `src/v2/ops/` (Pydantic parameter models) with their Lua implementations in `scripts/ops_*.lua`. Built-in ops: `create_sprite`, `open_sprite`, `save_sprite`, `close_session`, `draw_pixel`, `draw_rect`, `fill_region`, `clear_canvas`.

```python
apply_operations(ops=[
    {"op": "create_sprite", "width": 32, "height": 32},
    {"op": "draw_rect", "x": 4, "y": 4, "width": 24, "height": 24, "color": "#E74C3C", "filled": True},
    {"op": "draw_pixel", "x": 16, "y": 6, "color": "#FFFFFF"},
])
```

All drawing ops accept `layer` / `frame` (1-based, default 1/1). A batch runs inside one `app.transaction`, so `atomic=true` (the default) rolls the whole batch back if any op fails.

> [!TIP]
> `inspect` is the core of the workflow: after drawing, AI calls it to "see" the canvas, analyze it, and decide whether to fix it, forming a **draw → inspect → analyze → fix** loop.

---

##  Example Prompts

The prompt and implementation notes behind each row of the table at the top.

**Chibi Knight · 4 directions × 6 frames · 32x32**

> Use Aseprite MCP to generate a pixel art sprite sheet of a brave knight in silver armor holding a long sword, red plume and red cape. Four-direction walk cycle (down, up, left, right), 6 frames per direction, 32x32, flat colors, transparent background, 1px dark outline, light from the top-left.

Legs swing in anti-phase on `sin(2πt)`, the body sinks on each contact beat, and the cape and plume sway with the same phase — amplitudes are deliberately exaggerated so the motion still reads at the 4x size the asset ships at. The cloth also lags by half a frame (follow-through): a pure sine sampled at 6 evenly spaced points is symmetric, so two pairs of frames quantise to identical pixels and the GIF encoder silently merges them down to 4 frames.

---

**Dark Reaper · 4 directions × 6 frames · 32x32**

> Use Aseprite MCP to generate a pixel art sprite sheet of a dark reaper in a tattered black robe wielding a giant scythe, glowing red eyes under the hood. Four-direction walk cycle (down, up, left, right), 6 frames per direction, 32x32, flat colors, transparent background, 1px dark outline.

The reaper has no legs: the walk is carried by a travelling wave along the robe hem, a whole-body bob, and two bone feet alternating out from under the robe. In the front and back views the scythe blade must sweep outward from the body, otherwise it covers the hood entirely.

---

**Slime Devourer · 4 directions × 5 frames · 32x32**

> Use Aseprite MCP to generate a pixel art sprite sheet of a slime monster that devours its prey — green blob body, huge jaws, fangs. Four-direction devour animation (down, up, left, right), 5 frames per direction: idle → crouch → lunge with open maw → chomp → swallow. 32x32, flat colors, transparent background, sprite sheet layout.

This one shows an **action animation**, not just a walk cycle: all 20 frames live in one `.ase`, split by direction into 4 tags (`devour_down`, …), with per-phase frame durations (200/100/80/90/220 ms — the chomp snaps fastest, the swallow lingers). The side view is modelled as a skull ellipse and a jaw ellipse counter-rotating about the mouth hinge, which is what makes the open mouth a notch cut through the silhouette instead of a hole floating inside the body.

---

## 🤝 Contributing

Issues and Pull Requests are welcome!

I've tried it, but I can't guarantee it works perfectly. It still needs more optimization.

---

##  License

This project is open-sourced under the [MIT License](LICENSE).

Copyright © 2026 [ZhangDongyang800](https://github.com/ZhangDongyang800)

<div align="center">

<sub>Built with ❤️ for pixel art lovers</sub>

</div>
