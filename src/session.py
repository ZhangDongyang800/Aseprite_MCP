"""Session management.

Every session owns an isolated work directory holding one .ase canvas file.
Sessions are identified by session_id (a UUID) and can be created, looked up,
closed and swept on timeout.
"""

import re
import uuid
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, field

from src.config import Config

_UUID_DIR = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


@dataclass
class SessionManager:
    """Manage the lifecycle of drawing sessions.

    Each session keeps:
    - session_id: UUID string
    - work directory: <work_dir>/sessions/<session_id>/
    - .ase file: <work directory>/canvas.ase
    - canvas info: width, height, color_mode
    - timestamps: created_at, last_activity
    """

    config: Config

    # In-memory session store: session_id -> session data dict
    _sessions: dict = field(default_factory=dict, init=False, repr=False)

    def create_session(
        self, width: int, height: int, color_mode: str = "rgb"
    ) -> str:
        """Create a new session.

        Args:
            width: canvas width in pixels
            height: canvas height in pixels
            color_mode: color mode ("rgb", "grayscale", "indexed")

        Returns:
            session_id: UUID string of the new session
        """
        session_id = str(uuid.uuid4())
        now = time.time()

        # Create the work directory
        work_dir = self.config.sessions_dir / session_id
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"cannot create the session directory {work_dir}: {exc}. "
                f"Set ASEPRITE_WORK_DIR to a writable, ASCII-only path."
            ) from exc

        # Record the session data
        self._sessions[session_id] = {
            "session_id": session_id,
            "work_dir": work_dir,
            "ase_path": work_dir / "canvas.ase",
            "width": width,
            "height": height,
            "color_mode": color_mode,
            "created_at": now,
            "last_activity": now,
        }

        return session_id

    def _get_session(self, session_id: str) -> dict:
        """Fetch session data and refresh the last-activity timestamp.

        Args:
            session_id: session ID

        Returns:
            the session data dict

        Raises:
            KeyError: when the session does not exist
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")

        # Refresh the last-activity timestamp
        self._sessions[session_id]["last_activity"] = time.time()
        return self._sessions[session_id]

    def get_work_dir(self, session_id: str) -> Path:
        """Return the session's work directory."""
        return self._get_session(session_id)["work_dir"]

    def get_ase_path(self, session_id: str) -> Path:
        """Return the session's .ase canvas file path."""
        return self._get_session(session_id)["ase_path"]

    def get_canvas_info(self, session_id: str) -> dict:
        """Return the canvas metadata."""
        session = self._get_session(session_id)
        return {
            "width": session["width"],
            "height": session["height"],
            "color_mode": session["color_mode"],
        }

    def update_canvas_info(
        self, session_id: str, width: int, height: int
    ) -> None:
        """Refresh the session's cached canvas size.

        For flows like import_png: after importing an external file the real dimensions
        can differ from the placeholder size the session was created with, so the cache
        is refreshed to keep get_canvas_info returning the right values.

        Args:
            session_id: session ID
            width: real canvas width in pixels
            height: real canvas height in pixels
        """
        session = self._get_session(session_id)
        session["width"] = width
        session["height"] = height

    def close_session(self, session_id: str) -> None:
        """Close a session and delete its work directory.

        Args:
            session_id: session ID

        Raises:
            KeyError: when the session does not exist
        """
        session = self._get_session(session_id)
        work_dir = session["work_dir"]

        # Delete the work directory
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

        # Drop it from the in-memory registry
        del self._sessions[session_id]

    def list_sessions(self) -> list[dict]:
        """List every active session.

        Returns:
            list of session info dicts, each with session_id, width, height, color_mode
        """
        result = []
        for session_id, data in self._sessions.items():
            result.append({
                "session_id": session_id,
                "width": data["width"],
                "height": data["height"],
                "color_mode": data["color_mode"],
            })
        return result

    def _last_seen(self, entry: Path) -> float:
        """Newest mtime in a session directory; in-place .ase writes do not bump the parent."""
        newest = entry.stat().st_mtime
        for child in entry.iterdir():
            try:
                newest = max(newest, child.stat().st_mtime)
            except OSError:
                continue
        return newest

    def cleanup_expired(self) -> None:
        """Drop session directories that have gone quiet for session_timeout seconds.

        Scans the filesystem instead of the in-memory registry, so sessions orphaned by an
        earlier server process are collected too. Only UUID-named directories are touched —
        anything else the user keeps under the work dir is none of our business. The work dir
        root is scanned as well so sessions from before the `sessions/` layout still expire.
        """
        cutoff = time.time() - self.config.session_timeout
        for root in (self.config.sessions_dir, self.config.work_dir):
            if not root.is_dir():
                continue
            for entry in root.iterdir():
                if not entry.is_dir() or not _UUID_DIR.fullmatch(entry.name):
                    continue
                try:
                    stale = self._last_seen(entry) < cutoff
                except OSError:
                    continue
                if stale:
                    shutil.rmtree(entry, ignore_errors=True)
                    self._sessions.pop(entry.name, None)
