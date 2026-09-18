from pathlib import Path

from pydantic import BaseModel

from src.v2.compile import compile_ops, lua_string, lua_value, parse_result_stdout
from src.v2.registry import OpSpec


class _P(BaseModel):
    x: int
    color: str


def _spec():
    return OpSpec(
        name="draw_pixel", category="draw", params=_P,
        lua="_mcp_op_draw_pixel", mutating=True,
    )


def test_lua_string_escapes_control_and_quotes():
    assert lua_string('a"b') == '"a\\"b"'
    assert lua_string("a\nb") == '"a\\nb"'
    assert lua_string("a\x01b") == '"a\\1b"'
    assert lua_string("中文") == '"中文"'


def test_lua_value_nested():
    assert lua_value({"a": 1, "b": [True, None]}) == "{a=1,b={true,nil}}"
    assert lua_value({"not ident": "x"}) == '{["not ident"]="x"}'


def test_compile_contains_single_transaction_and_literal():
    spec = _spec()
    params = _P(x=3, color="#FF0000")
    src = compile_ops(
        [(spec, params)],
        file_path=Path("C:/w/canvas.ase"),
        scripts_dir=Path("C:/repo/scripts"),
        atomic=True,
    )
    assert "app.transaction(" in src
    assert "_mcp_op_draw_pixel" in src
    assert "{x=3,color=\"#FF0000\"}" in src
    assert src.count("app.transaction(") == 1
    assert "dofile" in src and "mcp_common.lua" in src


def test_compile_non_atomic_has_no_transaction():
    spec = _spec()
    src = compile_ops(
        [(spec, _P(x=1, color="#000000"))],
        file_path=Path("c.ase"), scripts_dir=Path("s"), atomic=False,
    )
    assert "app.transaction(" not in src


def test_parse_result_stdout():
    payload = '{\n"ops": []\n}'
    out = f"noise\n__MCP_JSON__{payload}\n"
    assert parse_result_stdout(out) == {"ops": []}
