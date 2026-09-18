import threading
from unittest.mock import MagicMock

from src.v2.result import ErrorCode


def test_run_lua_requires_unsafe(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    env = captured["run_lua"](session_id=sid, code="print(1)")
    assert env.ok is False
    assert env.error.code.value == "unsupported_in_mode"


def test_run_lua_unsafe_guard_precedes_session_check(tools):
    captured, _, _ = tools
    env = captured["run_lua"](session_id="missing", code="print(1)")
    assert env.ok is False
    assert env.error.code == ErrorCode.UNSUPPORTED_IN_MODE


def test_run_lua_requires_confirmed(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    env = captured["run_lua"](session_id=sid, code="print(1)", unsafe=True)
    assert env.ok is False
    assert env.error.code == ErrorCode.CONFIRMATION_REQUIRED
    assert env.error.hint == "re-call with confirmed=true"


def test_run_lua_confirmed_guard_precedes_session_check(tools):
    captured, _, _ = tools
    env = captured["run_lua"](
        session_id="missing", code="print(1)", unsafe=True, confirmed=False
    )
    assert env.ok is False
    assert env.error.code == ErrorCode.CONFIRMATION_REQUIRED


def test_run_lua_executes_when_unsafe(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {"success": True, "stdout": "1\n", "stderr": ""}
    env = captured["run_lua"](
        session_id=sid, code="print(1)", unsafe=True, confirmed=True
    )
    assert env.ok is True
    assert env.op_results[0].data["stdout"].strip() == "1"


def test_run_lua_passes_code_path_not_code(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {"success": True, "stdout": "", "stderr": ""}
    captured["run_lua"](
        session_id=sid, code="print(42)", unsafe=True, confirmed=True
    )

    snippet = sm.get_work_dir(sid) / "_run_lua.lua"
    assert snippet.read_text(encoding="utf-8") == "print(42)"
    script, params = runner.run_script.call_args[0]
    assert script == "mcp_run_lua.lua"
    assert params["file"] == str(sm.get_ase_path(sid))
    assert params["code_path"] == str(snippet)
    assert "code" not in params


def test_run_lua_uses_session_lock(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {"success": True, "stdout": "", "stderr": ""}
    engine = captured["_engine"]
    engine.session_lock = MagicMock()
    env = captured["run_lua"](
        session_id=sid, code="print(1)", unsafe=True, confirmed=True
    )
    assert env.ok is True
    engine.session_lock.assert_called_once_with(sid)


def test_run_lua_unknown_session(tools):
    captured, _, _ = tools
    env = captured["run_lua"](
        session_id="missing", code="print(1)", unsafe=True, confirmed=True
    )
    assert env.ok is False
    assert env.error.code == ErrorCode.SESSION_NOT_FOUND


def test_run_lua_runner_failure(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {
        "success": False, "error": "boom", "stderr": "trace",
    }
    env = captured["run_lua"](
        session_id=sid, code="error('x')", unsafe=True, confirmed=True
    )
    assert env.ok is False
    assert env.error.code == ErrorCode.LUA_RUNTIME_ERROR
    assert env.error.hint == "trace"


def test_engine_session_lock_serializes(tools):
    captured, sm, _ = tools
    engine = captured["_engine"]
    sid = sm.create_session(8, 8)
    first_inside = threading.Event()
    second_attempted = threading.Event()
    second_inside = threading.Event()
    release_first = threading.Event()

    def first():
        with engine.session_lock(sid):
            first_inside.set()
            release_first.wait(timeout=5)

    def second():
        first_inside.wait(timeout=5)
        second_attempted.set()
        with engine.session_lock(sid):
            second_inside.set()

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    try:
        assert first_inside.wait(timeout=5)
        assert second_attempted.wait(timeout=5)
        assert second_inside.wait(timeout=0.5) is False
        release_first.set()
        assert second_inside.wait(timeout=5)
    finally:
        release_first.set()
        t1.join(timeout=5)
        t2.join(timeout=5)
