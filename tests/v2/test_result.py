from src.v2.result import Envelope, ErrorCode, ErrorInfo, OpResult, UndoInfo


def test_failure_envelope_shape():
    env = Envelope.failure(
        ErrorCode.INVALID_ARGS, "bad op", hint="known ops: draw_rect", op_index=2
    )
    assert env.ok is False
    assert env.changed is False
    assert env.error is not None
    assert env.error.code == ErrorCode.INVALID_ARGS
    assert env.error.op_index == 2
    assert env.undo.available is False
    assert env.model_dump()["error"]["code"] == "invalid_args"


def test_success_envelope_roundtrip():
    env = Envelope(
        ok=True,
        session_id="s1",
        mode="cli",
        op_results=[OpResult(op="draw_rect", ok=True, data={"drawn": 1})],
        changed=True,
        undo=UndoInfo(mode="file_backup", available=True),
    )
    dumped = env.model_dump()
    assert dumped["op_results"][0]["op"] == "draw_rect"
    assert Envelope.model_validate(dumped).ok is True
