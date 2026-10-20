# tests/live — on-machine harnesses

These scripts are **not pytest tests** (their names deliberately do not match
`test_*.py` / `*_test.py`, so pytest never collects them): they launch a real MCP
server process and the real Aseprite executable, print a pass/fail report and
speak through their exit code. `pytest` itself stays fast and Aseprite-free; run
these by hand when you need on-machine evidence.

```bash
# Windows: tell the scripts where Aseprite is (PATH / common install locations
# are auto-detected as well)
set ASEPRITE_PATH=D:\path\to\aseprite.exe

python tests/live/probe_server_version.py       # does this checkout behave as specified?
python tests/live/live_smoke.py                 # runs core by default
python tests/live/live_smoke.py bounds gates runlua
python tests/live/live_smoke.py --all           # everything (incl. big-canvas timing, ~1 min)
python tests/live/ws_probe.py                   # the four WebSocket bridge segments
```

Intermediate artifacts land in `.build/` (gitignored).

## Why they exist

The e2e tests in pytest only cover "the server can run one real path end to end";
many of the contracts this round of fixes deals with are **only exposed against
real Aseprite**: out-of-bounds draws being dropped silently, `atomic=false`
rolling everything back, the `paint_grid` latch for files outside the work
directory, canvas rollback for failed batches, big-canvas flood-fill timeouts.
The two scripts above turn each of these contracts into an assertion instead of
treating "no error" as a pass.

## What each of the three scripts covers

| Script | Covers |
| --- | --- |
| `probe_server_version.py` | 4 assertions: out-of-bounds error, `atomic=false` partial success, a clean batch without warnings, the `paint_grid` latch |
| `live_smoke.py` | 8 scenarios: `core` (envelope + inspect + undo/redo), `codegen` (atomic / partial success), `atomic_rollback`, `bounds`, `gates`, `animation`, `runlua` (snapshot rollback), `perf` (2048/4096 timing budget) |
| `ws_probe.py` | 4 protocol segments: malformed response does not hang, simulated extension end to end (real `aseprite -b` runs the script), error quality without the extension, CLI fallback when the ws port is taken |

## Known limits

- Headless `aseprite -b` has **no undo history at all** (`app.command.Undo()` is
  a silent no-op), so the undo/redo checks in `live_smoke.py` only verify the
  file snapshot semantics of CLI mode; native multi-step undo can only be checked
  by hand in GUI Aseprite + Live mode.
- `ws_probe.py` uses a **simulated extension** (a fake ws client that runs each
  received script through a real `aseprite -b`), because the real
  `extension/main.lua` needs a GUI Aseprite session. The extension-side Lua
  behavior is currently covered only by code review.
- The `perf` budgets are loose upper bounds meant to catch order-of-magnitude
  regressions, not a performance SLA.
- A full 4096x4096 flood fill measures around 20s (Lua scans row by row: linear
  but not fast), while the default `ASEPRITE_TIMEOUT` is 30s — to fill the whole
  largest canvas, raise the timeout first.