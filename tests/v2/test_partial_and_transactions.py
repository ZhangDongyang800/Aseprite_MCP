"""atomic=false really means partial success; transactions are probed where they can work."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config
from src.session import SessionManager
from src.v2.compile import compile_ops
from src.v2.executor import Engine
from src.v2.ops.draw_ops import DrawPixel
from src.v2.ops.session_ops import CreateSprite
from src.v2.registry import OpRegistry, OpSpec
from src.v2.result import ErrorCode


def _partial_result(runner, sm, sid):
    """Simulate Lua: op 2 fails, ops 1 and 3 still get saved to disk."""
    path = sm.get_ase_path(sid)

    def run(*args, **kwargs):
        path.write_bytes(b"ASE-PARTIALLY-SAVED")
        return {
            "success": True,
            "stdout": "__MCP_JSON__" + json.dumps({
                "ops": [
                    {"op": "draw_pixel", "ok": True, "data": {}},
                    {"op": "draw_pixel", "ok": False, "data": "ops_draw.lua:11: layer not found: 5"},
                    {"op": "draw_pixel", "ok": True, "data": {}},
                ],
                "saved": True, "error": "layer not found: 5", "transaction": False,
            }),
            "stderr": "",
        }

    runner.run_script_path.side_effect = run


def test_non_atomic_batch_keeps_the_ops_that_worked(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE-BEFORE")
    _partial_result(runner, sm, sid)

    env = captured["apply_operations"](session_id=sid, atomic=False, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
        {"op": "draw_pixel", "x": 2, "y": 2, "color": "#00FF00", "layer": 5},
        {"op": "draw_pixel", "x": 3, "y": 3, "color": "#0000FF"},
    ])

    assert sm.get_ase_path(sid).read_bytes() == b"ASE-PARTIALLY-SAVED"
    assert [r.ok for r in env.op_results] == [True, False, True]
    assert env.changed is True
    assert any("partial" in w.lower() for w in env.warnings)
    assert any("layer not found: 5" in w for w in env.warnings)


def test_atomic_batch_still_rolls_everything_back(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE-BEFORE")
    _partial_result(runner, sm, sid)

    env = captured["apply_operations"](session_id=sid, atomic=True, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
        {"op": "draw_pixel", "x": 2, "y": 2, "color": "#00FF00", "layer": 5},
        {"op": "draw_pixel", "x": 3, "y": 3, "color": "#0000FF"},
    ])

    assert sm.get_ase_path(sid).read_bytes() == b"ASE-BEFORE"
    assert env.ok is False
    assert env.error.code is ErrorCode.OP_FAILED


def _compile(ops, *, atomic=True):
    return compile_ops(
        ops, file_path=Path("C:/w/sessions/x/canvas.ase"),
        scripts_dir=Path("C:/repo/scripts"), atomic=atomic,
    )


def _spec(name, params, lua):
    return OpSpec(name=name, category="draw", params=params, lua=lua, mutating=True)


def test_atomic_batch_probes_the_transaction_once_a_document_exists():
    src = _compile([
        (_spec("draw_pixel", DrawPixel, "_mcp_op_draw_pixel"),
         DrawPixel(x=1, y=1, color="#000000")),
        (_spec("draw_pixel", DrawPixel, "_mcp_op_draw_pixel"),
         DrawPixel(x=2, y=2, color="#000000")),
    ])

    # app.transaction raises when no document is open, so the document has to be resolved
    # (top-level, executed before) before the probe decides whether to transact.
    assert "local _ready_ok, _ready_err = pcall(_resolve)" in src
    assert src.index("pcall(_resolve)") < src.index("_tx_used = (")
    assert src.index("_tx_used = (") < src.index("pcall(app.transaction, _title, _body)")
    assert src.count("pcall(app.transaction,") == 2  # probe + the real transaction


def test_create_sprite_batch_probes_after_the_sprite_exists():
    src = _compile([
        (_spec("create_sprite", CreateSprite, "_mcp_op_create_sprite"),
         CreateSprite(width=16, height=16)),
        (_spec("draw_pixel", DrawPixel, "_mcp_op_draw_pixel"),
         DrawPixel(x=1, y=1, color="#000000")),
    ])

    # the opening op runs first and outside the transaction; only then can the probe work
    assert "local _ready_ok, _ready_err = pcall(function()" in src
    assert src.index("_mcp_op_create_sprite") < src.index("_tx_used = (")
    assert src.index("_tx_used = (") < src.index("pcall(app.transaction, _title, _body)")


def test_non_atomic_batch_still_saves_after_a_failed_op():
    src = _compile([
        (_spec("draw_pixel", DrawPixel, "_mcp_op_draw_pixel"),
         DrawPixel(x=1, y=1, color="#000000")),
    ], atomic=False)

    # Suppressing the save is what used to make "partial success" a lie.
    assert "_saved_ok = false" not in src
    assert "_run_error = _run_error or tostring(_data)" in src
    assert "_mcp_maybe_save(_sprite, _file)" in src


def test_inner_error_survives_the_transaction_wrapper():
    """The abort token must not overwrite the Lua message that names the failure."""
    src = _compile([
        (_spec("draw_pixel", DrawPixel, "_mcp_op_draw_pixel"),
         DrawPixel(x=1, y=1, color="#000000")),
    ])

    assert "_run_error = _run_error or tostring(_err)" in src
    assert "error(\"MCP_OP_FAILED:1\", 0)" in src


def _ws_engine(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "ws"
    sm = SessionManager(config)
    runner = MagicMock()
    return Engine(sm, runner, config), sm, runner


def test_live_mode_warning_does_not_claim_a_file_snapshot(tmp_path):
    engine, sm, runner = _ws_engine(tmp_path)
    sid = sm.create_session(8, 8)
    runner.run_script_path.return_value = {
        "success": True,
        "stdout": "__MCP_JSON__" + json.dumps({
            "ops": [{"op": "draw_pixel", "ok": True, "data": {}}],
            "saved": True, "error": None, "transaction": False,
        }),
        "stderr": "",
    }

    env = engine.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])

    assert env.warnings
    assert "file snapshot" not in env.warnings[0]
    assert "rollback" in env.warnings[0] or "undo" in env.warnings[0]