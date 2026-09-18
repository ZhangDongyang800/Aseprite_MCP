from pydantic import BaseModel

from src.v2.registry import OpRegistry, OpSpec
from src.v2.result import ErrorCode


class _Params(BaseModel):
    x: int
    color: str = "#000000"


def _registry() -> OpRegistry:
    reg = OpRegistry()
    reg.register(OpSpec(name="draw_pixel", category="draw", params=_Params, mutating=True))
    return reg


def test_validate_ok():
    reg = _registry()
    parsed, err = reg.validate([{"op": "draw_pixel", "x": 1}])
    assert err is None
    assert parsed[0][0].name == "draw_pixel"
    assert parsed[0][1].x == 1


def test_validate_unknown_op():
    reg = _registry()
    parsed, err = reg.validate([{"op": "nope"}])
    assert parsed == []
    assert err is not None and err.code == ErrorCode.INVALID_ARGS
    assert err.op_index == 0


def test_validate_bad_params_reports_index():
    reg = _registry()
    parsed, err = reg.validate(
        [{"op": "draw_pixel", "x": 1}, {"op": "draw_pixel", "x": "not-an-int"}]
    )
    assert err is not None and err.op_index == 1


def test_duplicate_registration_rejected():
    reg = _registry()
    try:
        reg.register(OpSpec(name="draw_pixel", category="draw", params=_Params))
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_catalog_is_json_schema_serializable():
    reg = _registry()
    catalog = reg.catalog()
    assert catalog[0]["name"] == "draw_pixel"
    assert catalog[0]["schema"]["properties"]["x"]["type"] == "integer"
