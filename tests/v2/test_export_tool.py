"""The export op's contract: artifacts are real files, and export never saves the document."""

import json

from src.v2.result import ErrorCode


def _payload(ops, saved=False):
    return {
        "success": True,
        "stdout": "__MCP_JSON__" + json.dumps({
            "ops": ops, "saved": saved, "error": None, "transaction": True,
        }),
        "stderr": "",
    }


def _session(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    return captured, sm, runner, sid


def test_export_returns_an_artifact_without_saving_the_document(tools, tmp_path):
    captured, sm, runner, sid = _session(tools)
    output = tmp_path / "out.png"
    output.write_bytes(b"PNG")
    runner.run_script_path.return_value = _payload([{
        "op": "export", "ok": True,
        "data": {"artifact_path": str(output), "artifact_kind": "png",
                 "width": 8, "height": 8, "frames": 1},
    }], saved=False)

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "export", "format": "png", "frame": 1, "output": str(output)},
    ])

    assert env.ok, env.error
    assert env.changed is False
    assert env.undo.available is False
    assert [a.path for a in env.artifacts] == [str(output)]
    assert env.artifacts[0].kind == "png"
    assert env.op_results[0].data["artifact_path"] == str(output)
    batch = (sm.get_work_dir(sid) / "_batch.lua").read_text(encoding="utf-8")
    assert "local _should_save = false" in batch
    assert "if _saved_ok and _should_save then" in batch


def test_export_missing_artifact_is_a_failure(tools, tmp_path):
    captured, _, runner, sid = _session(tools)
    missing = tmp_path / "missing.png"
    runner.run_script_path.return_value = _payload([{
        "op": "export", "ok": True,
        "data": {"artifact_path": str(missing), "artifact_kind": "png"},
    }], saved=False)

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "export", "format": "png", "frame": 1, "output": str(missing)},
    ])

    assert env.ok is False
    assert env.error.code == ErrorCode.FILE_ERROR
    assert "no usable file" in env.error.message
    assert env.changed is False


def test_export_rejects_wrong_extension_before_running_aseprite(tools, tmp_path):
    captured, _, runner, sid = _session(tools)
    runner.run_script_path.reset_mock()

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "export", "format": "gif", "output": str(tmp_path / "out.png")},
    ])

    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS
    runner.run_script_path.assert_not_called()


def test_export_frames_collects_every_artifact(tools, tmp_path):
    captured, _, runner, sid = _session(tools)
    paths = []
    for i in range(1, 4):
        path = tmp_path / f"frame{i}.png"
        path.write_bytes(b"PNG")
        paths.append(str(path))
    runner.run_script_path.return_value = _payload([{
        "op": "export", "ok": True,
        "data": {"artifact_paths": paths, "artifact_kind": "png",
                 "artifact_role": "frame", "frames": 3},
    }], saved=False)

    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "export", "format": "frames", "output": str(tmp_path / "frame.png")},
    ])

    assert env.ok, env.error
    assert [a.path for a in env.artifacts] == paths
    assert {a.role for a in env.artifacts} == {"frame"}
