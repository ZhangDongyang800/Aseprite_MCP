"""Tool-layer gates and side-effect hygiene: session provisioning, params, canvas metadata."""

import json

from src.v2.result import ErrorCode


def _ok_result(data=None, op="draw_pixel"):
    return {
        "success": True,
        "stdout": "__MCP_JSON__" + json.dumps({
            "ops": [{"op": op, "ok": True, "data": data or {}}],
            "saved": True, "error": None, "transaction": True,
        }),
        "stderr": "",
    }


def _fail_result(op, message):
    return {
        "success": True,
        "stdout": "__MCP_JSON__" + json.dumps({
            "ops": [{"op": op, "ok": False, "data": message}],
            "saved": False, "error": "MCP_OP_FAILED:1", "transaction": True,
        }),
        "stderr": "",
    }


def test_create_sprite_accepts_numeric_string_dimensions(tools):
    """'16.0' passes op validation, so session provisioning must not choke on it."""
    captured, sm, runner = tools
    runner.run_script_path.return_value = _ok_result(op="create_sprite")

    env = captured["apply_operations"](ops=[
        {"op": "create_sprite", "width": "16.0", "height": "8.0"},
    ])

    assert env.ok is True
    sizes = [(s["width"], s["height"]) for s in sm.list_sessions()]
    assert (16, 8) in sizes


def test_failed_first_op_does_not_leave_an_orphan_session(tools):
    captured, sm, runner = tools
    runner.run_script_path.return_value = _fail_result("open_sprite", "cannot open: D:/nope.ase")
    before = len(sm.list_sessions())

    env = captured["apply_operations"](ops=[
        {"op": "open_sprite", "path": "D:/nope.ase"},
    ])

    assert env.ok is False
    assert len(sm.list_sessions()) == before


def test_opened_sprite_session_reports_the_real_canvas_size(tools):
    captured, sm, runner = tools
    runner.run_script_path.return_value = _ok_result(
        {"width": 48, "height": 24, "frames": 3}, op="open_sprite")

    env = captured["apply_operations"](ops=[
        {"op": "open_sprite", "path": "D:/some/sprite.ase"},
    ])

    info = sm.get_canvas_info(env.session_id)
    assert (info["width"], info["height"]) == (48, 24)


def test_run_lua_gate_uses_its_own_error_code(tools):
    captured, _, _ = tools

    env = captured["run_lua"](session_id="whatever", code="print(1)")

    assert env.error.code.value == "unsafe_required"


def test_paint_grid_outside_the_work_dir_needs_confirmation(tools, tmp_path_factory):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    # the fixture's work dir is tmp_path, so the grid has to live in a sibling directory
    outside_dir = tmp_path_factory.mktemp("elsewhere")
    outside = outside_dir / "grid.lua"
    outside.write_text('return { palette = { k = "#000000" }, rows = { "kk" } }', encoding="utf-8")

    refused = captured["apply_operations"](session_id=sid, ops=[
        {"op": "paint_grid", "path": str(outside)},
    ])
    assert refused.ok is False
    assert refused.error.code is ErrorCode.CONFIRMATION_REQUIRED

    allowed = captured["apply_operations"](session_id=sid, ops=[
        {"op": "paint_grid", "path": str(outside)},
    ], confirmed=True)
    assert allowed.ok is True


def test_paint_grid_inside_the_session_work_dir_needs_no_confirmation(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    grid = sm.get_work_dir(sid) / "grid.lua"
    grid.write_text('return { palette = { k = "#000000" }, rows = { "kk" } }', encoding="utf-8")

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "paint_grid", "path": str(grid)},
    ])

    assert env.ok is True