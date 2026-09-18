from src.v2.ops import REGISTRY  # noqa: F401  触发注册
from src.v2.registry import REGISTRY as R


def test_expected_ops_registered():
    names = set(R.names())
    assert {"create_sprite", "open_sprite", "save_sprite", "close_session",
            "clear_canvas", "draw_pixel", "draw_rect", "fill_region"} <= names


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
