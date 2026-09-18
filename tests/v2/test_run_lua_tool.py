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


def test_run_lua_executes_when_unsafe(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {"success": True, "stdout": "1\n", "stderr": ""}
    env = captured["run_lua"](session_id=sid, code="print(1)", unsafe=True)
    assert env.ok is True
    assert env.op_results[0].data["stdout"].strip() == "1"


def test_run_lua_passes_code_path_not_code(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {"success": True, "stdout": "", "stderr": ""}
    captured["run_lua"](session_id=sid, code="print(42)", unsafe=True)

    snippet = sm.get_work_dir(sid) / "_run_lua.lua"
    assert snippet.read_text(encoding="utf-8") == "print(42)"
    script, params = runner.run_script.call_args[0]
    assert script == "mcp_run_lua.lua"
    assert params["file"] == str(sm.get_ase_path(sid))
    assert params["code_path"] == str(snippet)
    assert "code" not in params


def test_run_lua_unknown_session(tools):
    captured, _, _ = tools
    env = captured["run_lua"](session_id="missing", code="print(1)", unsafe=True)
    assert env.ok is False
    assert env.error.code == ErrorCode.SESSION_NOT_FOUND


def test_run_lua_runner_failure(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {
        "success": False, "error": "boom", "stderr": "trace",
    }
    env = captured["run_lua"](session_id=sid, code="error('x')", unsafe=True)
    assert env.ok is False
    assert env.error.code == ErrorCode.LUA_RUNTIME_ERROR
    assert env.error.hint == "trace"
