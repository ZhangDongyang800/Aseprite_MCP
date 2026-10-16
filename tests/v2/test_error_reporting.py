"""Failure reporting: the envelope must name the root cause and an actionable next step."""

import json

from src.v2.result import ErrorCode


def _run_result(ops, *, saved=False, error=None, transaction=True):
    body = {"ops": ops, "saved": saved, "error": error, "transaction": transaction}
    return {"success": True, "stdout": "__MCP_JSON__" + json.dumps(body), "stderr": ""}


def _session_with_canvas(sm):
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    return sid


def test_op_failure_message_names_the_cause_not_the_internal_sentinel(tools):
    captured, sm, runner = tools
    sid = _session_with_canvas(sm)
    runner.run_script_path.return_value = _run_result(
        [
            {"op": "draw_pixel", "ok": True, "data": {"x": 1, "y": 1}},
            {"op": "draw_pixel", "ok": False,
             "data": "D:/aseprite_mcp/scripts/ops_draw.lua:11: layer not found: 5"},
        ],
        error="MCP_OP_FAILED:2",
    )

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
        {"op": "draw_pixel", "x": 5, "y": 5, "color": "#0000FF", "layer": 5},
    ])

    assert env.error.code is ErrorCode.OP_FAILED
    # just the failure: no sentinel, no absolute script path, no line noise
    assert env.error.message == "layer not found: 5"
    assert env.error.op_index == 1


def test_failed_run_lua_reports_the_lua_error_not_the_exit_code(tools):
    captured, sm, runner = tools
    sid = _session_with_canvas(sm)
    runner.run_script.return_value = {
        "success": False,
        "stdout": "sessions/x/_run_lua.lua:1: boom",
        "stderr": "",
        "error": "Aseprite exited with code 4294967295",
    }

    env = captured["run_lua"](session_id=sid, code='error("boom")', unsafe=True, confirmed=True)

    assert env.error.code is ErrorCode.LUA_RUNTIME_ERROR
    assert "boom" in env.error.message
    assert "4294967295" not in env.error.message


def test_timeout_failure_suggests_how_to_get_unblocked(tools):
    captured, sm, runner = tools
    sid = _session_with_canvas(sm)
    runner.run_script_path.return_value = {
        "success": False, "stdout": "", "stderr": "",
        "error": "Aseprite script timeout: exceeded 30 seconds",
    }

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
    ])

    assert env.error.code is ErrorCode.SCRIPT_ERROR
    assert "timeout" in (env.error.message + env.error.hint).lower()
    assert "split" in env.error.hint.lower() or "smaller" in env.error.hint.lower()


def test_missing_aseprite_binary_is_reported_as_aseprite_not_found(tools):
    captured, sm, runner = tools
    sid = _session_with_canvas(sm)
    runner.run_script_path.return_value = {
        "success": False, "stdout": "", "stderr": "",
        "error": "Aseprite executable not found: aseprite",
    }

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
    ])

    assert env.error.code is ErrorCode.ASEPRITE_NOT_FOUND
    assert "ASEPRITE_PATH" in env.error.hint


def test_first_mutation_without_a_prior_canvas_reports_no_undo(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)  # no canvas.ase yet: nothing was overwritten, nothing to undo
    runner.run_script_path.return_value = _run_result(
        [{"op": "draw_pixel", "ok": True, "data": {"x": 1, "y": 1}}], saved=True, error=None)

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
    ])

    assert env.ok is True
    assert env.undo.available is False


def test_second_mutation_reports_undo_available(tools):
    captured, sm, runner = tools
    sid = _session_with_canvas(sm)
    runner.run_script_path.return_value = _run_result(
        [{"op": "draw_pixel", "ok": True, "data": {"x": 1, "y": 1}}], saved=True, error=None)

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
    ])

    assert env.undo.available is True