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


def test_apply_operations_rejects_unknown_param(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_rect", "x": 0, "y": 0, "width": 2, "height": 2,
         "color": "#FF0000", "colur": "#00FF00"}
    ])
    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS


def test_create_sprite_rejects_misspelled_param(tools):
    captured, sm, _ = tools
    before = len(sm.list_sessions())
    env = captured["apply_operations"](ops=[
        {"op": "create_sprite", "width": 8, "height": 8, "widht": 8}
    ])
    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS
    assert len(sm.list_sessions()) == before


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


def test_dry_run_does_not_create_session(tools):
    captured, sm, _ = tools
    before = len(sm.list_sessions())
    env = captured["apply_operations"](
        ops=[{"op": "create_sprite", "width": 8, "height": 8}], dry_run=True
    )
    assert env.ok is True
    assert len(sm.list_sessions()) == before


def test_dry_run_does_not_close_session(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    env = captured["apply_operations"](
        session_id=sid, ops=[{"op": "close_session"}],
        confirmed=True, dry_run=True,
    )
    assert env.ok is True
    assert sid in [s["session_id"] for s in sm.list_sessions()]


def test_unconfirmed_destructive_batch_does_not_create_session(tools):
    captured, sm, _ = tools
    before = len(sm.list_sessions())
    env = captured["apply_operations"](ops=[
        {"op": "create_sprite", "width": 8, "height": 8},
        {"op": "clear_canvas"},
    ], confirmed=False)
    assert env.ok is False
    assert env.error.code == ErrorCode.CONFIRMATION_REQUIRED
    assert len(sm.list_sessions()) == before


def test_apply_operations_undo_routes_to_engine(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    path = sm.get_ase_path(sid)
    path.write_bytes(b"AFTER")
    (path.parent / "undo_backup.ase").write_bytes(b"BEFORE")
    runner.run_script_path.reset_mock()

    env = captured["apply_operations"](session_id=sid, ops=[{"op": "undo"}])
    assert env.ok is True
    assert env.op_results[0].op == "undo"
    assert path.read_bytes() == b"BEFORE"
    runner.run_script_path.assert_not_called()


def test_apply_operations_redo_routes_to_engine(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    path = sm.get_ase_path(sid)
    path.write_bytes(b"BEFORE")
    (path.parent / "redo_backup.ase").write_bytes(b"AFTER")
    runner.run_script_path.reset_mock()

    env = captured["apply_operations"](session_id=sid, ops=[{"op": "redo"}])
    assert env.ok is True
    assert env.op_results[0].op == "redo"
    assert path.read_bytes() == b"AFTER"
    runner.run_script_path.assert_not_called()


def test_apply_operations_undo_missing_session(tools):
    captured, _, _ = tools
    env = captured["apply_operations"](ops=[{"op": "undo"}])
    assert env.ok is False
    assert env.error.code == ErrorCode.SESSION_NOT_FOUND


def test_apply_operations_undo_must_be_single_op(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 0, "y": 0, "color": "#000000"},
        {"op": "undo"},
    ])
    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS
    assert env.error.hint == "undo/redo must be a single-op batch"
