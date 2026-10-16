"""Shared helpers for the on-machine harnesses in tests/live/.

These scripts are **not** pytest tests (their names deliberately don't match
``test_*.py`` / ``*_test.py``): they drive a real Aseprite through a real MCP stdio
session and print a pass/fail report with a meaningful exit code. pytest stays fast
and Aseprite-free; run these by hand when you want evidence from the real binary:

    python tests/live/probe_server_version.py     # is the repo build behaving as specified?
    python tests/live/live_smoke.py bounds gates  # on-machine regression scenarios
    python tests/live/ws_probe.py                 # websocket bridge protocol

``ASEPRITE_PATH`` must point at an Aseprite binary (or one must be installed normally);
the location order is env var -> PATH -> common install locations, same as the server.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = Path(__file__).resolve().parent / ".build"
WORK = BUILD / "work"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.aseprite_locate import locate_aseprite  # noqa: E402

# the envelope shape apply_operations/run_lua promise (see src/v2/result.py)
ENVELOPE_FIELDS = ("ok", "session_id", "mode", "op_results", "artifacts",
                   "warnings", "changed", "undo", "timing_ms", "error")


def require_aseprite() -> str:
    path = locate_aseprite()
    if not path:
        sys.exit("Aseprite not found - set ASEPRITE_PATH=<path to aseprite>")
    return path


def env_for(mode: str = "cli", port: int = 9071) -> dict:
    env = dict(os.environ)
    env.pop("ASEPRITE_MCP_MODE", None)          # never inherit the caller's mode
    env["ASEPRITE_PATH"] = require_aseprite()
    env["ASEPRITE_WORK_DIR"] = str(WORK)
    env["ASEPRITE_WS_PORT"] = str(port)
    if mode != "cli":
        env["ASEPRITE_MCP_MODE"] = mode
    return env


def transport(mode: str = "cli", port: int = 9071):
    from fastmcp.client.transports import StdioTransport

    WORK.mkdir(parents=True, exist_ok=True)
    return StdioTransport(command=sys.executable, args=[str(ROOT / "server.py")],
                          env=env_for(mode, port))


def brief(env: dict | None) -> dict:
    """Trim an envelope to the fields worth reading in a report."""
    env = env or {}
    return {k: env.get(k) for k in
            ("ok", "changed", "mode", "session_id", "warnings", "undo", "op_results", "error")}


def metrics_of(structured: dict | None) -> dict:
    return (structured or {}).get("metrics", {})


class Report:
    """Collects named checks so the harness can exit non-zero on a real regression."""

    def __init__(self, scenario: str):
        self.scenario = scenario
        self.checks: list[dict] = []

    def check(self, label: str, ok: bool, detail: object = "") -> bool:
        self.checks.append({"check": label, "ok": bool(ok), "detail": detail})
        return bool(ok)

    def equal(self, label: str, got: object, want: object) -> bool:
        return self.check(label, got == want, f"got {got!r}, want {want!r}")

    def contains(self, label: str, haystack: object, needle: str) -> bool:
        return self.check(label, needle in str(haystack),
                          f"{needle!r} not in {str(haystack)[:160]!r}")

    @property
    def failures(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]

    def dump(self) -> str:
        lines = [f"== {self.scenario}"]
        for c in self.checks:
            mark = "ok  " if c["ok"] else "FAIL"
            line = f"   [{mark}] {c['check']}"
            # detail is diagnostic: it only earns screen space when something broke
            if not c["ok"] and c["detail"] != "":
                line += f"  -- {c['detail']}"
            lines.append(line)
        lines.append(f"   -> {len(self.checks) - len(self.failures)}/{len(self.checks)} checks passed")
        return "\n".join(lines)


def finish(reports: list[Report]) -> int:
    for report in reports:
        print(report.dump())
    failed = sum(len(r.failures) for r in reports)
    total = sum(len(r.checks) for r in reports)
    print(f"\n{total - failed}/{total} checks passed across {len(reports)} scenario(s)")
    if failed:
        print("FAILED checks:")
        for r in reports:
            for c in r.failures:
                print(f"  - {r.scenario}: {c['check']} ({c['detail']})")
        return 1
    print("OK: real-machine behaviour matches the contracts")
    return 0