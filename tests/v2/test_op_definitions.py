import pytest
from pydantic import ValidationError

from src.v2.ops import REGISTRY  # noqa: F401  触发注册
from src.v2.registry import REGISTRY as R


def test_expected_ops_registered():
    names = set(R.names())
    assert {"create_sprite", "open_sprite", "save_sprite", "close_session",
            "clear_canvas", "draw_pixel", "draw_rect", "fill_region",
            "add_frames", "add_tag", "paint_grid"} <= names


def test_draw_defaults():
    spec = R.get("draw_pixel")
    params = spec.params.model_validate({"x": 1, "y": 2, "color": "#FF0000"})
    assert params.layer == 1 and params.frame == 1
    assert spec.mutating is True


def test_create_sprite_requires_size():
    spec = R.get("create_sprite")
    params = spec.params.model_validate({"width": 16, "height": 16})
    assert params.color_mode == "rgb"


def test_close_session_is_destructive():
    assert R.get("close_session").destructive is True


def test_add_frames_defaults_and_bounds():
    params = R.get("add_frames").params.model_validate({"count": 3})
    assert params.duration == 0.1 and params.duplicate is False
    for bad in ({"count": 0}, {"count": 1, "duration": 0}, {"count": 1, "blank": True}):
        with pytest.raises(ValidationError):
            R.get("add_frames").params.model_validate(bad)


def test_add_tag_needs_a_name_and_range():
    params = R.get("add_tag").params.model_validate(
        {"name": "idle", "from_frame": 1, "to_frame": 4})
    assert params.name == "idle"
    for bad in ({"from_frame": 1, "to_frame": 2}, {"name": "x", "from_frame": 0, "to_frame": 2},
                {"name": "x", "from_frame": 1, "to_frame": 2, "from": 1}):
        with pytest.raises(ValidationError):
            R.get("add_tag").params.model_validate(bad)


def test_paint_grid_defaults_to_the_whole_first_frame():
    params = R.get("paint_grid").params.model_validate({"path": "D:/tmp/a.json"})
    assert (params.layer, params.frame, params.x, params.y) == (1, 1, 0, 0)
    with pytest.raises(ValidationError):
        R.get("paint_grid").params.model_validate({"path": "a.json", "rows": [".."]})


def test_set_durations_are_seconds_and_bounded():
    params = R.get("set_durations").params.model_validate({"durations": [0.16, 0.11]})
    assert params.durations == [0.16, 0.11]
    for bad in ({"durations": []}, {"durations": [0]}, {"durations": [0.1, 200]},
                {"durations": [160]}):
        with pytest.raises(ValidationError):
            R.get("set_durations").params.model_validate(bad)


@pytest.mark.parametrize("name", ["add_frames", "add_tag", "paint_grid"])
def test_structure_ops_are_compiled_lua_not_meta(name):
    spec = R.get(name)
    assert spec.lua and spec.mutating and not spec.destructive


@pytest.mark.parametrize("name", ["undo", "redo"])
def test_undo_redo_are_meta_ops(name):
    spec = R.get(name)
    assert spec.category == "meta"
    assert spec.mutating is True
    assert spec.lua is None
    spec.params.model_validate({})
    with pytest.raises(ValidationError):
        spec.params.model_validate({"x": 1})
