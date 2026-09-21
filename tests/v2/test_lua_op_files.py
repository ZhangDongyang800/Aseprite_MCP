from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def test_op_libraries_exist_with_functions():
    for fname, funcs in {
        "ops_session.lua": ["_mcp_op_create_sprite", "_mcp_op_open_sprite", "_mcp_op_save_sprite"],
        "ops_draw.lua": [
            "_mcp_op_clear_canvas", "_mcp_op_draw_pixel",
            "_mcp_op_draw_rect", "_mcp_op_fill_region", "_mcp_op_paint_grid",
        ],
        "ops_structure.lua": ["_mcp_op_add_frames", "_mcp_op_set_durations", "_mcp_op_add_tag"],
    }.items():
        text = (SCRIPTS / fname).read_text(encoding="utf-8")
        for fn in funcs:
            assert f"function _G.{fn}" in text, f"{fn} missing in {fname}"


def test_op_libraries_guard_common_load():
    for fname in ["ops_session.lua", "ops_draw.lua", "ops_structure.lua"]:
        text = (SCRIPTS / fname).read_text(encoding="utf-8")
        assert "_mcp_common_loaded" in text


def test_save_sprite_without_path_errors_when_unsaved():
    text = (SCRIPTS / "ops_session.lua").read_text(encoding="utf-8")
    assert 'error("no filename' in text
