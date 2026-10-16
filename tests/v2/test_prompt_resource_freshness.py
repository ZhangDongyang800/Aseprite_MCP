"""Prompts / Resources 新鲜度测试。

这两个模块是交给 AI 看的散文。一旦它们提到一个已经不存在的工具名，
客户端就会照着调用一个没有注册的 tool，进入必然失败的重试循环。

所以本文件做两件事：
  1. 反向断言 —— 渲染后的 prompt / resource 正文（以及 resource 描述，
     它同样随资源清单发给客户端）里不得出现任何"死工具名"标识符。
  2. 正向断言 —— 真实的三工具词汇（apply_operations / inspect / run_lua）
     和它们教的 op 名必须可被查到，否则提示词就等于没说。

prompt / resource 都是普通函数，直接调用渲染即可，不需要起 MCP server。
"""

import re
from unittest.mock import MagicMock

import pytest

from src.prompts import register_prompts
from src.resources import register_resources


# 49 工具时代遗留、现已不存在于工具面的名字。
# 注意 add_frame 不是 add_frames、set_palette_color 不是别的 op —— 下面用
# 标识符切分而不是子串匹配，所以这些前缀冲突天然安全。
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

# 真实工具面：三个工具，以及它们内部可用的全部 op。
LIVE_TOOLS = ("apply_operations", "inspect", "run_lua")
LIVE_OPS = (
    "create_sprite", "open_sprite", "save_sprite", "close_session",
    "draw_pixel", "draw_rect", "fill_region", "paint_grid", "clear_canvas",
    "add_frames", "set_durations", "add_tag", "undo", "redo",
)

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _dead_names_in(text: str) -> set:
    """文本中出现的死工具名集合（按标识符切分，不做子串匹配）。"""
    tokens = set(_IDENTIFIER.findall(text))
    return {name for name in DEAD_NAMES if name in tokens}


@pytest.fixture(scope="module")
def prompts():
    """注册到 mock mcp 上的 prompt 函数集合。"""
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
    """注册到 mock mcp 上的 resource 函数集合（含描述）。"""
    captured = {}
    mcp = MagicMock()

    def capture_resource(uri=None, **kwargs):
        def decorator(func):
            captured[uri or func.__name__] = func
            return func
        return decorator

    mcp.resource = capture_resource

    session_manager = MagicMock()
    session_manager.list_sessions.return_value = [
        {"session_id": "s1", "width": 16, "height": 16, "color_mode": "rgb"},
    ]
    session_manager.get_canvas_info.return_value = {
        "width": 16, "height": 16, "color_mode": "rgb",
    }
    register_resources(mcp, session_manager)
    return captured


PROMPT_ARGS = {
    "create_sprite_prompt": {"description": "一个红色的蘑菇", "size": "16x16"},
    "iterate_sprite_prompt": {"session_id": "s1", "feedback": "圆形不够圆"},
    "create_animation_prompt": {"description": "行走循环", "frame_count": 4, "fps": 8},
    "animation_consistency_prompt": {"description": "挥剑攻击", "frame_count": 6, "fps": 12},
    "multi_layer_prompt": {"description": "带背景的角色场景", "layer_count": 3},
    "create_tileset_prompt": {"description": "草地与泥土过渡瓦片"},
}


def test_dead_list_stays_disjoint_from_the_live_op_registry():
    """死名单不能和真实 op 注册表重叠。

    否则有两种坏结果：要么一个还活着的 op 被当成死名，从提示词里删掉；
    要么有人重新注册了 add_layer 之类的 op，这份测试还在逼着删它。
    """
    import src.v2.ops  # noqa: F401  触发 op 注册
    from src.v2.registry import REGISTRY

    registered = set(REGISTRY.names())
    assert registered == set(LIVE_OPS), "op 词汇表变了，同步更新 LIVE_OPS / DEAD_NAMES"
    assert not DEAD_NAMES & registered, (
        f"这些名字其实还活着，不该当死名: {sorted(DEAD_NAMES & registered)}"
    )


def test_all_prompts_still_registered(prompts):
    """六个 prompt 都还在，签名没变。"""
    assert set(prompts) == set(PROMPT_ARGS)


@pytest.mark.parametrize("name", sorted(PROMPT_ARGS))
def test_prompts_contain_no_dead_tool_names(prompts, name):
    """prompt 正文不得再教 AI 调用已删除的工具。"""
    body = prompts[name](**PROMPT_ARGS[name])
    assert _dead_names_in(body) == set(), f"{name} 仍在引用死工具: {sorted(_dead_names_in(body))}"


def test_rendered_prompts_mention_the_real_tool_surface(prompts):
    """正向断言：三个真工具名必须出现在 prompt 里。"""
    bodies = [prompts[name](**PROMPT_ARGS[name]) for name in sorted(PROMPT_ARGS)]
    everything = "\n".join(bodies)
    for tool in LIVE_TOOLS:
        assert tool in everything, f"没有任何 prompt 提到 {tool}"


def test_sprite_prompt_teaches_the_real_vocabulary(prompts):
    """创作引导必须教 apply_operations / inspect / paint_grid / save_sprite。"""
    body = prompts["create_sprite_prompt"](**PROMPT_ARGS["create_sprite_prompt"])
    for name in ("apply_operations", "inspect", "create_sprite", "paint_grid",
                 "save_sprite", "draw_pixel"):
        assert name in body, f"create_sprite_prompt 没有提到 {name}"


def test_animation_prompts_teach_the_structural_ops(prompts):
    """动画引导必须用 add_frames / set_durations / add_tag，而不是已删的帧工具。"""
    for name in ("create_animation_prompt", "animation_consistency_prompt"):
        body = prompts[name](**PROMPT_ARGS[name])
        for op in ("add_frames", "set_durations", "add_tag"):
            assert op in body, f"{name} 没有提到 {op}"


def test_prompts_are_honest_about_layers_and_the_escape_hatch(prompts):
    """没有 add_layer op —— 必须说清多层要走 run_lua，且 run_lua 需要双开关。"""
    body = prompts["multi_layer_prompt"](**PROMPT_ARGS["multi_layer_prompt"])
    assert "run_lua" in body
    assert "unsafe" in body and "confirmed" in body
    # 图层提示里不能再暗示有个 add_layer 之类的 op（已被 DEAD_NAMES 覆盖），
    # 并且要正面承认 layer>1 需要先造层。
    assert "layer" in body


def test_prompts_document_the_destructive_confirmation_gate(prompts):
    """clear_canvas / close_session 是破坏性 op，必须写明需要 confirmed=true。"""
    body = prompts["create_sprite_prompt"](**PROMPT_ARGS["create_sprite_prompt"])
    assert "clear_canvas" in body
    assert "confirmed=true" in body


# ══════════════════════════════════════════
# Resources
# ══════════════════════════════════════════

# 客户端依赖的 URI 清单：注册时用带花括号的模板形式，调用时给具体参数。
# 覆盖全部 14 个注册 URI，并对每个 tips/standards 分类各渲染一次。
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

# 全部注册 URI（含模板），一个不多一个不少。
ALL_RESOURCE_URIS = {uri for uri, _ in RESOURCE_CALLS}


def test_registered_resource_uris_are_exactly_the_documented_set(resources):
    """客户端按 URI 取数据，URI 集合必须原样保持。"""
    assert set(resources) == ALL_RESOURCE_URIS


@pytest.mark.parametrize("uri,args", RESOURCE_CALLS, ids=[u for u, _ in RESOURCE_CALLS])
def test_resource_bodies_contain_no_dead_tool_names(resources, uri, args):
    """resource 正文不得提到死工具。"""
    body = resources[uri](*args)
    assert _dead_names_in(body) == set(), f"{uri} 仍在引用死工具: {sorted(_dead_names_in(body))}"


def test_resource_descriptions_contain_no_dead_tool_names(resources):
    """resource 描述随清单发给客户端，同样不得承诺不存在的工具。"""
    for uri, func in resources.items():
        dead = _dead_names_in(func.__doc__ or "")
        assert dead == set(), f"{uri} 的描述仍在引用死工具: {sorted(dead)}"


def test_module_level_prose_contains_no_dead_tool_names():
    """模块级数据（tips/patterns/standards）的散文部分也不能提死工具。"""
    import src.resources as resources_module

    rendered = []
    for attr in ("_PIXEL_ART_TIPS", "_SPRITE_PATTERNS", "_STANDARDS",
                 "_TIMING_PRESETS", "_TILESET_TEMPLATES", "_PRESET_PALETTES"):
        import json
        rendered.append(json.dumps(getattr(resources_module, attr), ensure_ascii=False))
    dead = _dead_names_in("\n".join(rendered))
    assert dead == set(), f"资源数据里仍在引用死工具: {sorted(dead)}"


def test_resource_data_is_still_intact(resources):
    """修散文不能修数据：调色板/模板/预设的内容照旧。"""
    import json

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