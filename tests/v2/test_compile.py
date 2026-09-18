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
    assert lua_string("a\x01b") == '"a\\x01b"'
    assert lua_string("中文") == '"中文"'


def test_lua_string_control_escape_is_unambiguous():
    assert lua_string("a\x012b") == '"a\\x012b"'
    assert lua_string("\x1b" + "3") == '"\\x1b3"'


def test_lua_value_nested():
    assert lua_value({"a": 1, "b": [True, None]}) == "{a=1,b={true,nil}}"
    assert lua_value({"not ident": "x"}) == '{["not ident"]="x"}'


def test_lua_value_quotes_lua_keywords_and_non_ascii_keys():
    assert lua_value({"end": 1}) == '{["end"]=1}'
    assert lua_value({"nil": 1}) == '{["nil"]=1}'
    assert lua_value({"中": 1}) == '{["中"]=1}'
    assert lua_value({"_ok1": 2}) == "{_ok1=2}"


def test_compile_atomic_probes_transaction_and_uses_body():
    spec = _spec()
    params = _P(x=3, color="#FF0000")
    src = compile_ops(
        [(spec, params)],
        file_path=Path("C:/w/canvas.ase"),
        scripts_dir=Path("C:/repo/scripts"),
        atomic=True,
    )
    assert "_mcp_op_draw_pixel" in src
    assert "{x=3,color=\"#FF0000\"}" in src
    assert "local _body = function()" in src
    # 探测 + 真实执行，共两处 app.transaction（均以 pcall(app.transaction, ...) 形式调用）
    assert src.count("app.transaction") == 2
    assert src.count("pcall(app.transaction,") == 2
    assert "transaction=_tx_used" in src
    assert "dofile" in src and "mcp_common.lua" in src


def test_compile_non_atomic_has_no_transaction():
    spec = _spec()
    src = compile_ops(
        [(spec, _P(x=1, color="#000000"))],
        file_path=Path("c.ase"), scripts_dir=Path("s"), atomic=False,
    )
    assert "app.transaction(" not in src
    assert "transaction=_tx_used" in src  # 非原子路径报告 transaction=false


def test_compile_non_bootstrap_calls_resolve():
    spec = _spec()
    src = compile_ops(
        [(spec, _P(x=1, color="#000000"))],
        file_path=Path("c.ase"), scripts_dir=Path("s"), atomic=False,
    )
    assert "pcall(_mcp_op_draw_pixel, _resolve(), {x=1,color=\"#000000\"})" in src
    assert ", _sprite," not in src


def test_compile_create_sprite_bootstrap_uses_created_sprite():
    spec = OpSpec(
        name="create_sprite", category="draw", params=_P,
        lua="_mcp_op_create_sprite", mutating=True,
    )
    src = compile_ops(
        [(spec, _P(x=16, color="#FFFFFF"))],
        file_path=Path("c.ase"), scripts_dir=Path("s"), atomic=False,
    )
    assert "pcall(_mcp_op_create_sprite, nil, {x=16,color=\"#FFFFFF\"})" in src
    assert "_sprite = _G._mcp_created_sprite" in src


def test_parse_result_stdout():
    payload = '{\n"ops": []\n}'
    out = f"noise\n__MCP_JSON__{payload}\n"
    assert parse_result_stdout(out) == {"ops": []}
