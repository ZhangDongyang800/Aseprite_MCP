import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastmcp.tools import ToolResult
from PIL import Image as PILImage

from src.v2.inspect import compute_metrics

META = {"width": 2, "height": 2, "frames": [], "layers": [], "palette": [], "tags": []}


def _png(tmp_path: Path) -> Path:
    img = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(4):
        img.putpixel((x, 0), (255, 0, 0, 255))
    img.putpixel((7, 7), (0, 255, 0, 128))
    p = tmp_path / "p.png"
    img.save(p)
    return p


def _write_preview(script, params):
    img = PILImage.new("RGBA", (2, 2), (0, 0, 0, 0))
    img.putpixel((0, 0), (255, 0, 0, 255))
    img.save(params["output"])
    return {"success": True, "stdout": json.dumps(META), "stderr": ""}


def test_compute_metrics(tmp_path):
    m = compute_metrics(
        _png(tmp_path), {"width": 8, "height": 8, "frames": [], "layers": []}
    )
    assert m["color_count"] == 2
    assert m["semi_transparent_pixels"] == 1
    assert m["coverage"] == 5 / 64
    assert m["bbox"] == {"x": 0, "y": 0, "width": 8, "height": 8}
    assert m["isolated_pixels"] == 1


def test_near_duplicate_detection(tmp_path):
    img = PILImage.new("RGBA", (4, 4), (0, 0, 0, 0))
    img.putpixel((0, 0), (100, 100, 100, 255))
    img.putpixel((1, 0), (102, 100, 100, 255))
    p = tmp_path / "q.png"
    img.save(p)
    m = compute_metrics(p, {"width": 4, "height": 4, "frames": [], "layers": []})
    assert m["near_duplicate_colors"]


def test_inspect_calls_script_with_session_path_and_writes_preview(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_preview

    result = captured["inspect"](session_id=sid)

    work = sm.get_work_dir(sid)
    runner.run_script.assert_called_once_with(
        "inspect.lua",
        {
            "file": str(sm.get_ase_path(sid)),
            "output": str(work / "preview.png"),
            "scale": "4",
            "view": "composite",
        },
    )
    assert (work / "preview.png").exists()
    assert isinstance(result, ToolResult)
    assert result.content[0].type == "image"
    assert result.structured_content["meta"] == META
    assert result.structured_content["metrics"]["color_count"] == 1
    saved = json.loads((work / "metrics.json").read_text(encoding="utf-8"))
    assert saved == result.structured_content


def test_inspect_passes_scale_and_view(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_preview

    captured["inspect"](session_id=sid, scale=8, view="silhouette")

    _, params = runner.run_script.call_args[0]
    assert params["scale"] == "8"
    assert params["view"] == "silhouette"


def test_inspect_holds_session_lock(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_preview
    engine = captured["_engine"]
    engine.session_lock = MagicMock()

    captured["inspect"](session_id=sid)

    engine.session_lock.assert_called_once_with(sid)


def test_inspect_unknown_session(tools):
    captured, _, _ = tools
    with pytest.raises(ValueError, match="session not found"):
        captured["inspect"](session_id="missing")


def test_inspect_runner_failure(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.return_value = {"success": False, "error": "boom"}

    with pytest.raises(RuntimeError, match="boom"):
        captured["inspect"](session_id=sid)
