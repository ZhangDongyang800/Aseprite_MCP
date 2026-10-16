"""Live-mode native undo/redo must not claim success for a no-op."""

from unittest.mock import MagicMock

from src.config import Config
from src.session import SessionManager
from src.v2.executor import Engine
from src.v2.result import ErrorCode


def _engine(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "ws"
    sm = SessionManager(config)
    return Engine(sm, MagicMock(), config), sm


def _reply(stdout: str) -> dict:
    return {"success": True, "stdout": stdout, "stderr": ""}


def test_native_undo_reports_when_aseprite_history_is_empty(tmp_path):
    engine, sm = _engine(tmp_path)
    sid = sm.create_session(8, 8)
    engine.runner.run_script.return_value = _reply("NOTHING: undo (Aseprite history is empty)")

    env = engine.undo(sid)

    assert env.ok is False
    assert env.error.code is ErrorCode.NO_MORE_UNDO
    assert "nothing" in env.error.message.lower()


def test_native_redo_reports_when_there_is_nothing_to_redo(tmp_path):
    engine, sm = _engine(tmp_path)
    sid = sm.create_session(8, 8)
    engine.runner.run_script.return_value = _reply("NOTHING: redo")

    env = engine.redo(sid)

    assert env.ok is False
    assert env.error.code is ErrorCode.NO_MORE_REDO


def test_native_undo_succeeds_when_the_document_actually_moved(tmp_path):
    engine, sm = _engine(tmp_path)
    sid = sm.create_session(8, 8)
    engine.runner.run_script.return_value = _reply("OK: undo")

    env = engine.undo(sid)

    assert env.ok is True
    assert env.undo.mode == "transaction"