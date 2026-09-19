from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def test_inspect_never_resizes_source():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    # 缩放只能发生在临时副本上
    assert "Sprite(sprite)" in text or "Sprite(_sprite)" in text
    assert "sprite:resize" not in text
    assert "_mcp_get_sprite" in text
    assert "saveCopyAs" in text


def test_inspect_prints_json_marker():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    assert "json.encode" in text


def test_inspect_lua_supports_silhouette():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    assert 'view == "silhouette"' in text
    assert "pixelColor.rgbaA" in text


def test_inspect_lua_scale_param_fallback():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    assert 'tonumber(app.params["scale"] or "4") or 4' in text


def test_inspect_lua_requires_metrics_output():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    assert 'error("metrics_output is required")' in text


def test_inspect_lua_metrics_copy_precedes_recolour_and_resize():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    metrics_idx = text.index("preview:saveCopyAs(metrics_output)")
    silhouette_idx = text.index('view == "silhouette"')
    resize_idx = text.index("preview:resize")
    output_idx = text.index("preview:saveCopyAs(output)")
    assert metrics_idx < silhouette_idx < resize_idx < output_idx


def test_inspect_lua_frame_param_defaults_to_first():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    assert 'tonumber(app.params["frame"] or "1") or 1' in text


def test_inspect_lua_collapses_multi_frame_copy_before_export():
    """多帧文档上 saveCopyAs 会写成 name1.png..nameN.png，副本必须先压成单帧。"""
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    assert text.index("deleteFrame") < text.index("preview:saveCopyAs(metrics_output)")
    # 删帧只允许发生在临时副本上
    assert "sprite:deleteFrame" not in text
