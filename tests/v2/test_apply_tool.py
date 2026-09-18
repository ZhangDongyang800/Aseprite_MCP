from src.v2.result import ErrorCode


def test_apply_operations_happy_path(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}
    ])
    assert env.ok is True
    assert env.changed is True
    assert runner.run_script_path.called


def test_apply_operations_unknown_op(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    env = captured["apply_operations"](session_id=sid, ops=[{"op": "nope"}])
    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS


def test_apply_operations_missing_session(tools):
    captured, _, _ = tools
    env = captured["apply_operations"](session_id="missing", ops=[
        {"op": "draw_pixel", "x": 0, "y": 0, "color": "#000000"}
    ])
    assert env.ok is False
    assert env.error.code == ErrorCode.SESSION_NOT_FOUND


def test_apply_operations_session_created_by_first_op(tools):
    captured, sm, _ = tools
    env = captured["apply_operations"](ops=[
        {"op": "create_sprite", "width": 8, "height": 8}
    ])
    assert env.ok is True
    assert env.session_id in [s["session_id"] for s in sm.list_sessions()]
