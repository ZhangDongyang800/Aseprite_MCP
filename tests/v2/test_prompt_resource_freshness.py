"""Prompts/resources must not teach the model tools or ops that no longer exist.

This is the guard against the v1 -> v2 migration drift: prose is shipped to the
client on every list, so a dead tool name becomes a guaranteed failed retry.
One table-driven pass per surface replaces the per-string parametrisation.
"""

import json
import re
from unittest.mock import MagicMock

import pytest

from src.prompts import register_prompts
from src.resources import register_resources

# Names from the retired v1 tool surface. add_frame != add_frames, so this is
# matched by identifier, never by substring.
DEAD_NAMES = frozenset({
    "draw_from_grid", "get_canvas_preview", "clear_region", "add_outline",
    "mirror_half", "replace_color", "export_gif", "add_frame",
    "set_frame_duration", "apply_timing_preset", "check_canvas_standards",
    "add_layer", "get_layer_info", "set_layer_properties", "propagate_cels",
    "tween_cel", "compare_frames", "export_contact_sheet",
    "create_tileset_canvas", "export_tiled_preview", "batch_edit",
    "import_png", "load_palette", "apply_palette", "append_palette",
    "set_palette_color", "resize_palette", "get_palette",
    "draw_animation_frames", "export_onion_skin", "select_all", "deselect",
    "select_by_color", "invert_selection", "delete_selection",
    "adjust_colors", "apply_blur", "get_frame_info", "get_tags",
    "duplicate_frame", "remove_frame", "remove_tag", "duplicate_layer",
    "remove_layer", "merge_down", "flatten", "flip_canvas", "rotate_canvas",
    "resize_sprite", "crop_sprite", "draw_line", "draw_ellipse",
    "draw_gradient", "create_sprite_canvas", "move_cel",
    "tween_cel_positions", "tween_cel_scale", "tween_cel_opacity",
})

LIVE_TOOLS = ("apply_operations", "inspect", "run_lua")
LIVE_OPS = (
    "create_sprite", "open_sprite", "save_sprite", "close_session",
    "draw_pixel", "draw_rect", "fill_region", "paint_grid", "clear_canvas",
    "add_frames", "set_durations", "add_tag", "export", "undo", "redo",
)
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _dead_names_in(text: str) -> set:
    tokens = set(_IDENTIFIER.findall(text))
    return {name for name in DEAD_NAMES if name in tokens}


@pytest.fixture(scope="module")
def prompts():
    captured = {}
    mcp = MagicMock()

    def capture_prompt(func=None, **kwargs):
        if func is None:
            return lambda f: capture_prompt(f, **kwargs)
        captured[func.__name__] = func
        return func

    mcp.prompt = capture_prompt
    register_prompts(mcp)
    return captured


@pytest.fixture(scope="module")
def resources():
    captured = {}
    mcp = MagicMock()

    def capture_resource(uri=None, **kwargs):
        def decorator(func):
            captured[uri or func.__name__] = func
            return func
        return decorator

    mcp.resource = capture_resource
    manager = MagicMock()
    manager.list_sessions.return_value = [
        {"session_id": "s1", "width": 16, "height": 16, "color_mode": "rgb"},
    ]
    manager.get_canvas_info.return_value = {
        "width": 16, "height": 16, "color_mode": "rgb",
    }
    register_resources(mcp, manager)
    return captured


PROMPT_ARGS = {
    "create_sprite_prompt": {"description": "一个红色的蘑菇", "size": "16x16"},
    "iterate_sprite_prompt": {"session_id": "s1", "feedback": "圆形不够圆"},
    "create_animation_prompt": {"description": "行走循环", "frame_count": 4, "fps": 8},
    "animation_consistency_prompt": {"description": "挥剑攻击", "frame_count": 6, "fps": 12},
    "multi_layer_prompt": {"description": "带背景的角色场景", "layer_count": 3},
    "create_tileset_prompt": {"description": "草地与泥土过渡瓦片"},
}

RESOURCE_CALLS = [
    ("aseprite://sessions", ()),
    ("aseprite://palette/default", ()),
    ("aseprite://palette/presets", ()),
    ("aseprite://palette/presets/{name}", ("db32",)),
    ("aseprite://timing/presets", ()),
    ("aseprite://timing/presets/{type}", ("walk",)),
    ("aseprite://blendmodes", ()),
    ("aseprite://anidirs", ()),
    ("aseprite://patterns", ()),
    ("aseprite://patterns/{name}", ("heart_16x16",)),
    ("aseprite://tileset/templates", ()),
    ("aseprite://tileset/templates/{name}", ("grass_dirt_16x16",)),
    ("aseprite://canvas/{session_id}/info", ("s1",)),
]
RESOURCE_CALLS += [("aseprite://tips/{category}", (c,)) for c in
                   ("basic_rules", "shading", "outline", "symmetry", "animation", "workflow")]
RESOURCE_CALLS += [("aseprite://standards/{category}", (c,)) for c in
                   ("size", "palette", "timing", "pixel_art")]
ALL_RESOURCE_URIS = {uri for uri, _ in RESOURCE_CALLS}


def test_dead_list_stays_disjoint_from_the_live_op_registry():
    import src.v2.ops  # noqa: F401  trigger op registration
    from src.v2.registry import REGISTRY

    registered = set(REGISTRY.names())
    assert registered == set(LIVE_OPS), "op vocabulary changed; update LIVE_OPS/DEAD_NAMES"
    assert not DEAD_NAMES & registered


def test_all_surfaces_are_registered(prompts, resources):
    assert set(prompts) == set(PROMPT_ARGS)
    assert set(resources) == ALL_RESOURCE_URIS


def test_prompts_contain_no_dead_names_and_teach_the_real_vocabulary(prompts):
    bodies = []
    for name, args in PROMPT_ARGS.items():
        body = prompts[name](**args)
        bodies.append(body)
        assert _dead_names_in(body) == set(), f"{name} references retired tools"
    everything = "\n".join(bodies)
    for tool in LIVE_TOOLS:
        assert tool in everything
    for op in ("create_sprite", "paint_grid", "save_sprite", "add_frames",
               "set_durations", "add_tag", "export"):
        assert op in everything, f"no prompt teaches {op}"


def test_prompts_are_honest_about_the_escape_hatch_and_gate(prompts):
    body = prompts["multi_layer_prompt"](**PROMPT_ARGS["multi_layer_prompt"])
    assert "run_lua" in body and "unsafe" in body and "confirmed" in body
    create = prompts["create_sprite_prompt"](**PROMPT_ARGS["create_sprite_prompt"])
    assert "clear_canvas" in create and "confirmed=true" in create


def test_resource_bodies_descriptions_and_module_prose_have_no_dead_names(resources):
    texts = []
    for uri, args in RESOURCE_CALLS:
        texts.append(resources[uri](*args))
    for uri, func in resources.items():
        texts.append(func.__doc__ or "")
    import src.resources as module
    for attr in ("_PIXEL_ART_TIPS", "_SPRITE_PATTERNS", "_STANDARDS",
                 "_TIMING_PRESETS", "_TILESET_TEMPLATES", "_PRESET_PALETTES"):
        texts.append(json.dumps(getattr(module, attr), ensure_ascii=False))
    dead = set().union(*(_dead_names_in(t) for t in texts))
    assert dead == set(), f"resources reference retired tools: {sorted(dead)}"


def test_resource_data_is_still_intact(resources):
    assert len(json.loads(resources["aseprite://palette/default"]())["colors"]) == 16
    assert set(json.loads(resources["aseprite://palette/presets"]())["presets"]) == {
        "db16", "db32", "aap64", "nes", "gameboy",
    }
    tile = json.loads(resources["aseprite://tileset/templates/{name}"]("grass_dirt_16x16"))
    assert tile["tile_size"] == 16
    assert tile["colormap"] == "G=#4A7C20,D=#8B5A2B,.=transparent"
    assert len(tile["grid"].split("/")) == 16
    assert json.loads(resources["aseprite://timing/presets/{type}"]("walk"))["duration_ms"] == 125
    assert "heart_16x16" in json.loads(resources["aseprite://patterns"]())["patterns"]
