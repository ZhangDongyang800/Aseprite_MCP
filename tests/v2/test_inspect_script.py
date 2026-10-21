"""Two source-order guards for bugs that only a real Aseprite exposes.

Everything else about inspect.lua is covered by the inspect metrics/tool tests
and the live smoke harness; grepping the rest of the source duplicates them.
"""

from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
INSPECT = SCRIPTS / "inspect.lua"


def test_inspect_never_resizes_the_source_document():
    text = INSPECT.read_text(encoding="utf-8")
    assert "Sprite(sprite)" in text or "Sprite(_sprite)" in text
    assert "sprite:resize" not in text
    assert "saveCopyAs" in text


def test_inspect_collapses_the_copy_to_one_frame_before_export():
    """A multi-frame saveCopyAs writes name1.png..nameN.png, never name.png."""
    text = INSPECT.read_text(encoding="utf-8")
    assert text.index("deleteFrame") < text.index("preview:saveCopyAs(metrics_output)")
    assert "sprite:deleteFrame" not in text
