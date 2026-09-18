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
