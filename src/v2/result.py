"""统一结果信封与稳定错误分类（spec §7）。"""

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
