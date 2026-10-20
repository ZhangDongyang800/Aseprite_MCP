"""Unified result envelope with stable error classification (spec §7)."""

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    INVALID_ARGS = "invalid_args"
    SESSION_NOT_FOUND = "session_not_found"
    ASEPRITE_NOT_FOUND = "aseprite_not_found"
    UNSUPPORTED_IN_MODE = "unsupported_in_mode"
    OP_FAILED = "op_failed"
    SCRIPT_ERROR = "script_error"
    LUA_RUNTIME_ERROR = "lua_runtime_error"
    FILE_ERROR = "file_error"
    NO_MORE_UNDO = "no_more_undo"
    NO_MORE_REDO = "no_more_redo"
    CONFIRMATION_REQUIRED = "confirmation_required"
    UNSAFE_REQUIRED = "unsafe_required"


class ErrorInfo(BaseModel):
    code: ErrorCode
    message: str
    hint: str = ""
    op_index: Optional[int] = None


class OpResult(BaseModel):
    op: str
    ok: bool
    data: Any = None


class Artifact(BaseModel):
    kind: Literal["png", "gif", "json", "ase"]
    path: str
    role: str


class UndoInfo(BaseModel):
    mode: Literal["transaction", "file_backup"] = "file_backup"
    available: bool = False


_LUA_LOCATION = re.compile(r"^[^\n]*?:\d+: ")


def clean_lua_error(text: str) -> str:
    """'D:/repo/scripts/ops_draw.lua:11: layer not found: 5' -> 'layer not found: 5'.

    Aseprite tracebacks are multi-line and open with a useless stack-traceback header; the
    line that names the failure is the one carrying a "<source>:<line>: " location prefix.
    Absolute paths and line numbers are noise for the caller, so they go.
    """
    if not isinstance(text, str):
        return str(text)
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    for line in lines:
        cleaned = _LUA_LOCATION.sub("", line, count=1).strip()
        if cleaned:
            return cleaned
    return lines[-1] if lines else text


def script_diagnostics(result: dict) -> tuple[str, str]:
    """(message, hint) for a failed Aseprite run.

    Headless Aseprite writes Lua errors to stdout and leaves stderr empty, so stdout has to be
    reported too or the caller is handed a bare exit code with nothing to act on. The message
    is the one line naming the failure; the hint keeps everything else (full traceback plus
    the transport summary) so no diagnosis is lost.
    """
    detail = "\n".join(
        part for part in ((result.get("stdout") or "").strip(),
                          (result.get("stderr") or "").strip()) if part
    )[:2000]
    summary = result.get("error") or ""
    if detail:
        message = clean_lua_error(detail)
    else:
        message = summary or "Aseprite script failed"
    hint_parts = [part for part in (detail, summary) if part and part != message]
    return message, "\n".join(hint_parts)[:2000]


_TIMEOUT_HINT = (
    "Aseprite did not finish in time. Split the batch into smaller calls, paint onto a "
    "smaller canvas, or raise the limit with ASEPRITE_TIMEOUT."
)
_MISSING_HINT = (
    "Aseprite was not found. Set ASEPRITE_PATH to the Aseprite executable and restart the "
    "MCP server (see README)."
)


def classify_script_failure(result: dict) -> tuple[ErrorCode, str, str]:
    """Map a failed Aseprite run onto (code, message, hint).

    Separates "Aseprite is missing" and "the script ran out of time" from genuine script
    errors so the caller can act on them instead of reading a raw exit code.
    """
    message, hint = script_diagnostics(result)
    lowered = f"{result.get('error') or ''} {hint}".lower()
    if "not found" in lowered and ("aseprite" in lowered or "executable" in lowered):
        return ErrorCode.ASEPRITE_NOT_FOUND, message, _MISSING_HINT
    if "timeout" in lowered or "timed out" in lowered:
        return ErrorCode.SCRIPT_ERROR, message, _TIMEOUT_HINT
    return ErrorCode.SCRIPT_ERROR, message, hint


class Envelope(BaseModel):
    ok: bool
    session_id: Optional[str] = None
    mode: Literal["cli", "ws"] = "cli"
    op_results: list[OpResult] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    changed: bool = False
    undo: UndoInfo = Field(default_factory=UndoInfo)
    timing_ms: int = 0
    error: Optional[ErrorInfo] = None

    @classmethod
    def failure(
        cls,
        code: ErrorCode,
        message: str,
        *,
        hint: str = "",
        op_index: Optional[int] = None,
        session_id: Optional[str] = None,
        mode: str = "cli",
        op_results: Optional[list[OpResult]] = None,
    ) -> "Envelope":
        return cls(
            ok=False,
            session_id=session_id,
            mode=mode,
            op_results=op_results or [],
            changed=False,
            undo=UndoInfo(),
            error=ErrorInfo(code=code, message=message, hint=hint, op_index=op_index),
        )
