"""Configuration management.

Reads settings from environment variables and supplies sensible defaults.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _warn_unusable_work_dir(path: Path) -> None:
    """Complain at startup instead of failing every later call obscurely.

    Aseprite 1.3.17 loads scripts and dofiles from non-ASCII paths fine (verified against a
    real headless run), but older builds and some console code pages choke on them and report
    it as a missing Lua engine - which reads as a build problem rather than a config one. So
    this is advice, not a hard failure.
    """
    if not str(path).isascii():
        print(
            f"NOTE: ASEPRITE_WORK_DIR is not ASCII-only: {path}\n"
            f"Current Aseprite builds handle this, but if scripts start failing to load with "
            f"'missing Lua engine', point ASEPRITE_WORK_DIR at an ASCII path.",
            file=sys.stderr,
        )


@dataclass
class Config:
    """MCP server configuration.

    Override the defaults through environment variables:
    - ASEPRITE_PATH: path to the Aseprite executable
    - ASEPRITE_WORK_DIR: root of the session work directories (default <repo>/work)
    - ASEPRITE_SESSION_TIMEOUT: session timeout (seconds)
    - ASEPRITE_TIMEOUT: per-call Aseprite timeout (seconds, default 30; relax it for
      big-canvas fill/blur)
    - ASEPRITE_MCP_MODE: execution mode ("cli" or "ws"), default "cli"
    - ASEPRITE_WS_HOST: address the WebSocket server listens on, default "127.0.0.1"
    - ASEPRITE_WS_PORT: port the WebSocket server listens on, default 9001
    """

    # Path to the Aseprite executable (defaults to the user's own build)
    aseprite_path: str = None

    # Session work directory
    work_dir: Path = None

    # Session timeout (seconds)
    session_timeout: int = None

    # Lua script directory (located automatically, not configurable via env vars)
    scripts_dir: Path = None

    # Execution mode: "cli" (classic CLI subprocess) or "ws" (live WebSocket mode)
    mode: str = None

    # WebSocket server settings (only used when mode="ws")
    ws_host: str = None
    ws_port: int = None

    # Time budget for one Aseprite call (seconds): a big-canvas fill/blur is an order of
    # magnitude slower than everyday drawing
    script_timeout: int = None

    def __post_init__(self):
        """Load configuration from environment variables and apply the defaults."""
        # Aseprite executable path
        if self.aseprite_path is None:
            from src.aseprite_locate import locate_aseprite

            self.aseprite_path = (
                os.environ.get("ASEPRITE_PATH")
                or locate_aseprite()
                or "aseprite"
            )

        # Session work directory: defaults to the repo root. A relative path would resolve
        # against whatever cwd the host handed the process - possibly unwritable, and it
        # scatters session files somewhere unexpected.
        if self.work_dir is None:
            self.work_dir = Path(
                os.environ.get("ASEPRITE_WORK_DIR") or _REPO_ROOT / "work"
            )
        self.work_dir = Path(self.work_dir).expanduser().resolve()
        _warn_unusable_work_dir(self.work_dir)

        # Session timeout
        if self.session_timeout is None:
            self.session_timeout = int(
                os.environ.get("ASEPRITE_SESSION_TIMEOUT", "3600")
            )

        # Per-script-call timeout (seconds): 30s by default; slow big-canvas workloads can
        # relax it with ASEPRITE_TIMEOUT
        if self.script_timeout is None:
            self.script_timeout = int(os.environ.get("ASEPRITE_TIMEOUT", "30"))

        # Lua script directory: resolved to scripts/ next to the src package's parent,
        # i.e. <project root>/scripts/
        self.scripts_dir = Path(__file__).parent.parent / "scripts"

        # Execution mode: cli (default) or ws (live WebSocket mode)
        if self.mode is None:
            self.mode = os.environ.get("ASEPRITE_MCP_MODE", "cli")

        # WebSocket server settings
        if self.ws_host is None:
            self.ws_host = os.environ.get("ASEPRITE_WS_HOST", "127.0.0.1")
        if self.ws_port is None:
            self.ws_port = int(os.environ.get("ASEPRITE_WS_PORT", "9001"))

    # Properties rather than fields: tests and callers reassign work_dir after construction.
    @property
    def sessions_dir(self) -> Path:
        """Where the server keeps session state. Nothing else belongs here."""
        return self.work_dir / "sessions"

    @property
    def appdata_dir(self) -> Path:
        """Stand-in %APPDATA% for hosts that strip it; infrastructure, not session data."""
        return self.work_dir / ".appdata"
