"""Real-Aseprite checks for the core gap fixes.

These are intentionally separate from test_e2e_v2.py so a capability regression has a
focused failure, and they auto-skip when no Aseprite is available.
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.aseprite_locate import locate_aseprite
from src.config import Config
from src.runner import AsepriteRunner
from src.session import SessionManager
from src.v2.tools import register_v2_tools

pytestmark = pytest.mark.e2e


def _resolve_aseprite() -> Path | None:
    env = os.environ.get("ASEPRITE_PATH")
    if env:
        return Path(env) if Path(env).exists() else None
    found = locate_aseprite()
    return Path(found) if found and Path(found).exists() else None


ASEPRITE = _resolve_aseprite()
skip_no_aseprite = pytest.mark.skipif(
    ASEPRITE is None, reason="Aseprite not found; set ASEPRITE_PATH"
)


@pytest.fixture
def api(tmp_path, monkeypatch):
    if ASEPRITE is None:
        pytest.skip("Aseprite not found; set ASEPRITE_PATH")
    monkeypatch.setenv("ASEPRITE_PATH", str(ASEPRITE))
    config = Config()
    config.work_dir = tmp_path / "work"
    config.work_dir.mkdir()
    config.mode = "cli"
    session_manager = SessionManager(config)
    runner = AsepriteRunner(config)
    if not runner.check_aseprite_exists():
        pytest.skip(f"Aseprite not usable at {config.aseprite_path}")

    captured = {}

    def capture(func=None, **kwargs):
        if func is None:
            return lambda f: capture(f, **kwargs)
        captured[func.__name__] = func
        return func

    mcp = MagicMock()
    mcp.tool = capture
    engine = register_v2_tools(mcp, session_manager, runner, config)
    return SimpleNamespace(
        apply=captured["apply_operations"],
        inspect=captured["inspect"],
        engine=engine,
        sm=session_manager,
        config=config,
    )


def _metrics(api, session_id, frame=1):
    result = api.inspect(session_id=session_id, scale=1, frame=frame)
    payload = result.structured_content
    assert payload["ok"], payload
    return payload["meta"], payload["metrics"]


def _grid(path: Path, rows: list[str], palette: dict[str, str]) -> None:
    pal = ", ".join(f'["{k}"] = "{v}"' for k, v in palette.items())
    body = ",\n".join(f'    "{row}"' for row in rows)
    path.write_text(
        f"return {{\n  palette = {{ {pal} }},\n  rows = {{\n{body},\n  }},\n}}\n",
        encoding="utf-8",
    )


@skip_no_aseprite
def test_create_sprite_reports_the_canvas_path(api):
    env = api.apply(ops=[{"op": "create_sprite", "width": 8, "height": 8}])
    assert env.ok, env.error
    created = next((r for r in env.op_results if r.op == "create_sprite"), None)
    assert created is not None, env.op_results
    assert created.data["canvas_path"] == str(api.sm.get_ase_path(env.session_id))


@skip_no_aseprite
def test_indexed_mode_paints_the_configured_palette(api):
    env = api.apply(ops=[
        {"op": "create_sprite", "width": 4, "height": 1, "color_mode": "indexed"},
    ])
    assert env.ok, env.error
    sid = env.session_id
    # Index 0 is Aseprite's transparent index. Keep it unused; paint the four visible
    # entries to prove that RGB -> palette-index mapping reaches indices 1..4.
    env = api.apply(session_id=sid, ops=[{
        "op": "set_palette",
        "colors": ["#14101E", "#D04648", "#DAD45E", "#5CCBAA", "#29ADFF"],
    }])
    assert env.ok, env.error

    grid = api.sm.get_work_dir(sid) / "indexed.lua"
    _grid(grid, ["bcde"], {
        "b": "#D04648", "c": "#DAD45E", "d": "#5CCBAA", "e": "#29ADFF",
    })
    env = api.apply(session_id=sid, ops=[{"op": "paint_grid", "path": str(grid)}])
    assert env.ok, env.error

    meta, metrics = _metrics(api, sid)
    assert meta["palette"] == ["#14101E", "#D04648", "#DAD45E", "#5CCBAA", "#29ADFF"]
    assert metrics["color_count"] == 4
    assert set(metrics["palette"]) == {"#D04648", "#DAD45E", "#5CCBAA", "#29ADFF"}


@skip_no_aseprite
def test_clear_canvas_layer_zero_clears_every_layer(api):
    env = api.apply(ops=[{"op": "create_sprite", "width": 4, "height": 4}])
    sid = env.session_id
    env = api.apply(session_id=sid, ops=[
        {"op": "add_layer", "name": "Top"},
        {"op": "draw_pixel", "layer": 1, "x": 0, "y": 0, "color": "#FF0000"},
        {"op": "draw_pixel", "layer": 2, "x": 1, "y": 1, "color": "#00FF00"},
    ])
    assert env.ok, env.error
    meta, before = _metrics(api, sid)
    assert before["color_count"] == 2
    assert [layer["name"] for layer in meta["layers"]] == ["Layer 1", "Top"]

    env = api.apply(session_id=sid, confirmed=True, ops=[
        {"op": "clear_canvas", "layer": 0},
    ])
    assert env.ok, env.error
    _, after = _metrics(api, sid)
    assert after["coverage"] == 0
    assert after["bbox"] is None


@skip_no_aseprite
def test_layer_and_line_ellipse_ops_are_usable(api):
    env = api.apply(ops=[{"op": "create_sprite", "width": 8, "height": 8}])
    sid = env.session_id
    env = api.apply(session_id=sid, ops=[
        {"op": "add_layer", "name": "FX"},
        {"op": "set_layer", "layer": 2, "opacity": 128, "visible": True},
        {"op": "draw_line", "layer": 1, "x1": 0, "y1": 0, "x2": 7, "y2": 0,
         "color": "#FF0000"},
        {"op": "draw_ellipse", "layer": 1, "cx": 4, "cy": 4, "rx": 2, "ry": 2,
         "color": "#00FF00", "filled": True},
    ])
    assert env.ok, env.error
    meta, metrics = _metrics(api, sid)
    assert meta["layers"][1]["opacity"] == 128
    assert meta["layers"][1]["visible"] is True
    assert set(metrics["palette"]) == {"#FF0000", "#00FF00"}
    assert metrics["bbox"] == {"x": 0, "y": 0, "width": 8, "height": 7}

    env = api.apply(session_id=sid, confirmed=True, ops=[
        {"op": "delete_layer", "layer": 2},
    ])
    assert env.ok, env.error
    meta, _ = _metrics(api, sid)
    assert len(meta["layers"]) == 1


@skip_no_aseprite
def test_inspect_reports_the_previous_frame_diff(api):
    env = api.apply(ops=[
        {"op": "create_sprite", "width": 4, "height": 4},
        {"op": "add_frames", "count": 1, "duplicate": False},
        {"op": "draw_pixel", "frame": 1, "x": 1, "y": 1, "color": "#FF0000"},
        {"op": "draw_pixel", "frame": 2, "x": 1, "y": 1, "color": "#0000FF"},
    ])
    assert env.ok, env.error
    sid = env.session_id
    _, first = _metrics(api, sid, frame=1)
    assert first["frame_diffs"] == []
    _, second = _metrics(api, sid, frame=2)
    assert second["frame_diffs"] == [{
        "from": 1, "to": 2, "changed_pixels": 1,
        "bbox": {"x": 1, "y": 1, "width": 1, "height": 1},
    }]
    assert "grid_offset" not in second


@skip_no_aseprite
def test_export_result_carries_durations_tags_and_sheet_rects(api, tmp_path):
    env = api.apply(ops=[{"op": "create_sprite", "width": 8, "height": 8}])
    sid = env.session_id
    env = api.apply(session_id=sid, ops=[
        {"op": "add_frames", "count": 1},
        {"op": "set_durations", "durations": [0.2, 0.3]},
        {"op": "add_tag", "name": "loop", "from_frame": 1, "to_frame": 2},
    ])
    assert env.ok, env.error

    sheet = tmp_path / "sheet.png"
    env = api.apply(session_id=sid, ops=[{
        "op": "export", "format": "sheet", "output": str(sheet),
        "layout": "horizontal",
    }])
    assert env.ok, env.error
    data = next(r.data for r in env.op_results if r.op == "export")
    assert data["durations"] == [0.2, 0.3]
    assert data["tags"] == [{"name": "loop", "from": 1, "to": 2}]
    assert data["frame_count"] == 2
    assert data["cell_width"] == 8 and data["cell_height"] == 8
    assert [r["frame"] for r in data["frame_rects"]] == [1, 2]
