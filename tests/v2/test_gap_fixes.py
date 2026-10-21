"""Unit-level contracts for the capability-gap fixes.

Lua is not executed here (same rule as the rest of tests/v2); the real-fragment checks
live in test_gap_fixes_e2e.py and auto-skip when Aseprite is absent.
"""

import json

import pytest
from PIL import Image as PILImage
from pydantic import ValidationError

from src.v2.inspect import compute_metrics, frame_diff
from src.v2.ops import REGISTRY
from src.v2.registry import REGISTRY as R


def test_new_core_ops_are_registered():
    assert {
        "draw_line", "draw_ellipse", "add_layer", "set_layer",
        "delete_layer", "set_palette",
    } <= set(R.names())


def test_clear_canvas_accepts_layer_zero_for_a_frame_wide_clear():
    spec = R.get("clear_canvas")
    params = spec.params.model_validate({"layer": 0, "frame": 2})
    assert (params.layer, params.frame) == (0, 2)
    assert spec.destructive is True
    with pytest.raises(ValidationError):
        spec.params.model_validate({"layer": -1})


def test_layer_and_palette_parameter_contracts():
    add = R.get("add_layer").params.model_validate({})
    assert (add.name, add.opacity) == ("Layer", 255)

    with pytest.raises(ValidationError):
        R.get("set_layer").params.model_validate({"layer": 1})
    with pytest.raises(ValidationError):
        R.get("set_layer").params.model_validate({"layer": 1, "opacity": 256})
    set_layer = R.get("set_layer").params.model_validate(
        {"layer": 2, "name": "FX", "visible": False})
    assert set_layer.layer == 2 and set_layer.visible is False

    assert R.get("delete_layer").destructive is True
    palette = R.get("set_palette").params.model_validate(
        {"colors": ["#000000", "#FFAA00"]})
    assert palette.colors == ["#000000", "#FFAA00"]
    with pytest.raises(ValidationError):
        R.get("set_palette").params.model_validate({"colors": ["#GGGGGG"]})
    with pytest.raises(ValidationError):
        R.get("set_palette").params.model_validate({"colors": []})


def test_line_and_ellipse_contracts():
    line = R.get("draw_line").params.model_validate(
        {"x1": 0, "y1": 0, "x2": 3, "y2": 2, "color": "#FF0000"})
    assert (line.x1, line.y1, line.x2, line.y2) == (0, 0, 3, 2)

    ellipse = R.get("draw_ellipse").params.model_validate(
        {"cx": 4, "cy": 4, "rx": 2, "ry": 3, "color": "#00FF00"})
    assert ellipse.filled is False
    with pytest.raises(ValidationError):
        R.get("draw_ellipse").params.model_validate(
            {"cx": 4, "cy": 4, "rx": 0, "ry": 3, "color": "#00FF00"})


def test_frame_diff_is_pixel_exact(tmp_path):
    a = PILImage.new("RGBA", (4, 4), (0, 0, 0, 0))
    b = a.copy()
    b.putpixel((1, 2), (255, 0, 0, 255))
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa)
    b.save(pb)

    diff = frame_diff(pb, pa)

    assert diff["changed_pixels"] == 1
    assert diff["bbox"] == {"x": 1, "y": 2, "width": 1, "height": 1}
    assert frame_diff(pa, pa) == {"changed_pixels": 0, "bbox": None}

    c = PILImage.new("RGBA", (2, 2))
    pc = tmp_path / "c.png"
    c.save(pc)
    assert "frame sizes differ" in frame_diff(pa, pc)["error"]


def _write_inspect_outputs(script, params):
    preview = PILImage.new("RGBA", (2, 2), (0, 0, 0, 0))
    preview.putpixel((0, 0), (255, 0, 0, 255))
    preview.save(params["output"])
    current = PILImage.new("RGBA", (2, 2), (0, 0, 0, 0))
    current.putpixel((0, 0), (0, 0, 255, 255))
    current.save(params["metrics_output"])
    if params.get("metrics_prev_output"):
        previous = PILImage.new("RGBA", (2, 2), (0, 0, 0, 0))
        previous.putpixel((0, 0), (255, 0, 0, 255))
        previous.save(params["metrics_prev_output"])
    return {"success": True,
            "stdout": json.dumps({"width": 2, "height": 2, "frame": 2,
                                  "frames_total": 2, "frames": [], "layers": [],
                                  "palette": [], "tags": []}),
            "stderr": ""}


def test_inspect_adds_a_real_previous_frame_diff(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_inspect_outputs

    result = captured["inspect"](session_id=sid, frame=2, scale=1)

    assert result.is_error is False
    metrics = result.structured_content["metrics"]
    assert metrics["frame_diffs"] == [{
        "from": 1, "to": 2, "changed_pixels": 1,
        "bbox": {"x": 0, "y": 0, "width": 1, "height": 1},
    }]
    assert "grid_offset" not in metrics
    _, params = runner.run_script.call_args[0]
    assert params["metrics_prev_output"].endswith("metrics_prev.png")


def test_single_frame_inspect_imports_the_same_metrics_contract(tmp_path):
    img = PILImage.new("RGBA", (2, 2), (0, 0, 0, 0))
    img.putpixel((0, 0), (10, 20, 30, 255))
    p = tmp_path / "m.png"
    img.save(p)
    m = compute_metrics(p, {"width": 2, "height": 2, "frames": [], "layers": []})
    assert set(m) == {
        "width", "height", "color_count", "palette", "near_duplicate_colors",
        "bbox", "coverage", "semi_transparent_pixels", "isolated_pixels",
        "frame_diffs",
    }
