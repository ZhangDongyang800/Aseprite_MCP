import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.config import Config
from src.session import SessionManager
from src.v2.executor import Engine
from src.v2.registry import OpRegistry, OpSpec
from src.v2.result import ErrorCode

TRANSACTION_WARNING = "app.transaction unavailable; CLI atomicity enforced by file snapshot"


def _payload(ops, *, saved=True, error=None, transaction=None):
    body = {"ops": ops, "saved": saved, "error": error}
    if transaction is not None:
        body["transaction"] = transaction
    return {
        "success": True,
        "stdout": "__MCP_JSON__" + json.dumps(body),
        "stderr": "",
    }


class _DrawPixelParams(BaseModel):
    x: int = 0
    y: int = 0
    color: str = "#000000"


def _test_registry() -> OpRegistry:
    reg = OpRegistry()
    reg.register(OpSpec(
        name="draw_pixel", category="draw", params=_DrawPixelParams,
        lua="_mcp_op_draw_pixel", mutating=True,
    ))
    return reg


@pytest.fixture
def engine(tmp_path, monkeypatch):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "cli"
    # 真实 op 由 Task 1.6 全局注册；本任务用测试局部注册表注入，避免污染 REGISTRY。
    monkeypatch.setattr("src.v2.executor.REGISTRY", _test_registry())
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script_path.return_value = {
        "success": True,
        "stdout": '__MCP_JSON__{"ops":[{"op":"draw_pixel","ok":true,"data":{}}],"saved":true,"error":null}',
        "stderr": "",
    }
    return Engine(sm, runner, config), sm, runner


def _make_ase(sm, sid):
    path = sm.get_ase_path(sid)
    path.write_bytes(b"ASE")


def test_dry_run_does_not_run(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}], dry_run=True)
    assert env.ok is True
    assert env.changed is False
    runner.run_script_path.assert_not_called()


def test_apply_writes_batch_and_backs_up(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])
    assert env.ok is True
    assert env.changed is True
    work = sm.get_work_dir(sid)
    assert (work / "_batch.lua").exists()
    assert (work / "undo_backup.ase").exists()
    runner.run_script_path.assert_called_once()


def test_unknown_op_returns_invalid_args(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    env = eng.apply(sid, [{"op": "definitely_not_an_op"}])
    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS


def test_failed_cli_batch_restores_snapshot_and_keeps_undo_backup(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    path = sm.get_ase_path(sid)
    path.write_bytes(b"V1")
    work = sm.get_work_dir(sid)
    # 先做一次成功批量，产生 undo_backup.ase = V1（前一次成功批量的快照）
    assert eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}]).ok is True
    assert (work / "undo_backup.ase").read_bytes() == b"V1"

    def fail_after_partial_write(script, params):
        path.write_bytes(b"PARTIAL")  # 模拟失败批量已把部分结果写盘
        return _payload(
            [{"op": "draw_pixel", "ok": False, "data": "boom"}],
            saved=False, error="boom", transaction=False,
        )

    runner.run_script_path.side_effect = fail_after_partial_write
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])
    assert env.ok is False
    assert path.read_bytes() == b"V1"
    assert (work / "undo_backup.ase").read_bytes() == b"V1"
    assert not (work / "_batch_before.ase").exists()


def test_successful_cli_batch_promotes_snapshot_to_undo_backup(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    path = sm.get_ase_path(sid)
    path.write_bytes(b"V1")
    work = sm.get_work_dir(sid)

    def write_and_succeed(script, params):
        path.write_bytes(b"V2")
        return _payload([{"op": "draw_pixel", "ok": True, "data": {}}], transaction=True)

    runner.run_script_path.side_effect = write_and_succeed
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])
    assert env.ok is True
    assert path.read_bytes() == b"V2"
    assert (work / "undo_backup.ase").read_bytes() == b"V1"
    assert not (work / "_batch_before.ase").exists()


def test_success_without_transaction_adds_warning(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    runner.run_script_path.return_value = _payload(
        [{"op": "draw_pixel", "ok": True, "data": {}}], transaction=False
    )
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])
    assert env.ok is True
    assert TRANSACTION_WARNING in env.warnings


def test_failure_without_transaction_adds_warning(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    runner.run_script_path.return_value = _payload(
        [{"op": "draw_pixel", "ok": False, "data": "boom"}],
        saved=False, error="boom", transaction=False,
    )
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])
    assert env.ok is False
    assert TRANSACTION_WARNING in env.warnings


def test_undo_redo_roundtrip(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    path = sm.get_ase_path(sid)
    path.write_bytes(b"BEFORE")
    shutil.copy2(path, path.parent / "undo_backup.ase")
    path.write_bytes(b"AFTER")

    assert eng.undo(sid).ok is True
    assert path.read_bytes() == b"BEFORE"
    assert eng.redo(sid).ok is True
    assert path.read_bytes() == b"AFTER"


def test_undo_without_backup_is_honest(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.undo(sid)
    assert env.ok is False
    assert env.error.code == ErrorCode.NO_MORE_UNDO


def test_redo_without_backup_is_honest(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.redo(sid)
    assert env.ok is False
    assert env.error.code == ErrorCode.NO_MORE_REDO


def test_new_mutating_apply_clears_redo(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    assert eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}]).ok is True
    assert eng.undo(sid).ok is True
    work = sm.get_work_dir(sid)
    assert (work / "redo_backup.ase").exists()

    assert eng.apply(sid, [{"op": "draw_pixel", "x": 2, "y": 2, "color": "#00FF00"}]).ok is True
    assert not (work / "redo_backup.ase").exists()
    env = eng.redo(sid)
    assert env.ok is False
    assert env.error.code == ErrorCode.NO_MORE_REDO


def test_undo_redo_unknown_session_returns_envelope(engine):
    eng, sm, _ = engine
    env = eng.undo("does-not-exist")
    assert env.ok is False
    assert env.error.code == ErrorCode.SESSION_NOT_FOUND
    env = eng.redo("does-not-exist")
    assert env.ok is False
    assert env.error.code == ErrorCode.SESSION_NOT_FOUND


def test_live_undo_redo_use_native_without_backups(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "ws"
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}
    eng = Engine(sm, runner, config)
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)

    assert eng.undo(sid).ok is True
    assert eng.redo(sid).ok is True
    assert runner.run_script.call_count == 2


def test_live_undo_redo_ok_stdout_is_success(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "ws"
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script.return_value = {"success": True, "stdout": "OK: undo\n", "stderr": ""}
    eng = Engine(sm, runner, config)
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)

    assert eng.undo(sid).ok is True
    assert eng.redo(sid).ok is True


@pytest.mark.parametrize("stdout", ["ERROR: no active sprite", ""])
def test_live_undo_redo_error_stdout_is_failure(tmp_path, stdout):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "ws"
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script.return_value = {"success": True, "stdout": stdout, "stderr": ""}
    eng = Engine(sm, runner, config)
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)

    undo_env = eng.undo(sid)
    assert undo_env.ok is False
    assert undo_env.error.code == ErrorCode.LUA_RUNTIME_ERROR
    redo_env = eng.redo(sid)
    assert redo_env.ok is False
    assert redo_env.error.code == ErrorCode.LUA_RUNTIME_ERROR
