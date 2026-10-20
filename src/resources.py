"""MCP Resources: read-only data sources.

Exposes the session list, palettes, canvas info, blend-mode list and other read-only data.
"""

import json

from src.session import SessionManager


# Aseprite's default palette (the classic 16-color pixel-art palette)
_DEFAULT_PALETTE = [
    "#000000", "#1D2B53", "#7E2553", "#008751",
    "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
    "#FF004D", "#FFA300", "#FFEC27", "#00E436",
    "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA",
]

# Preset palette library (docs §4.3; values follow the published standards)
_PRESET_PALETTES = {
    "db16": {
        "name": "db16",
        "description": "DawnBringer 16 色，适合简单项目",
        "colors": [
            "#140C1C", "#442434", "#30346D", "#4E4A4E",
            "#854C30", "#346524", "#D04648", "#757161",
            "#597DCE", "#D27D2C", "#8595A1", "#6DAA2C",
            "#DAD45E", "#6E2EC6", "#992D2E", "#5CCBAA",
        ],
    },
    "db32": {
        "name": "db32",
        "description": "DawnBringer 32 色，最常用的平衡选择",
        "colors": [
            "#000000", "#222034", "#45283C", "#663931",
            "#8F563B", "#DF7126", "#D9A066", "#EEC39A",
            "#FBF236", "#99E550", "#6ABE30", "#37946E",
            "#4B692F", "#524B24", "#323C39", "#3F3F74",
            "#306082", "#5B6EE1", "#839973", "#6EE86E",
            "#5AC54F", "#8AE5A4", "#C4CFA1", "#DFEFCA",
            "#9E6E2E", "#B58B47", "#6E6056", "#AB5236",
            "#B86F50", "#5E3023", "#8C3F2D", "#5C1122",
        ],
    },
    "aap64": {
        "name": "aap64",
        "description": "AAP-64，Adigun Polack 设计的现代像素艺术 64 色标准",
        # Source of the values: lospec.com/palette-list/aap-64 (the authoritative
        # 64-color standard)
        "colors": [
            "#060608", "#141013", "#3B1725", "#73172D",
            "#B4202A", "#DF3E23", "#FA6A0A", "#F9A31B",
            "#FFD541", "#FFFC40", "#D6F264", "#9CDB43",
            "#59C135", "#14A02E", "#1A7A3E", "#24523B",
            "#122020", "#143464", "#285CC4", "#249FDE",
            "#20D6C7", "#A6FCDB", "#FFFFFF", "#FEF3C0",
            "#FAD6B8", "#F5A097", "#E86A73", "#BC4A9B",
            "#793A80", "#403353", "#242234", "#221C1A",
            "#322B28", "#71413B", "#BB7547", "#DBA463",
            "#F4D29C", "#DAE0EA", "#B3B9D1", "#8B93AF",
            "#6D758D", "#4A5462", "#333941", "#422433",
            "#5B3138", "#8E5252", "#BA756A", "#E9B5A3",
            "#E3E6FF", "#B9BFFB", "#849BE4", "#588DBE",
            "#477D85", "#23674E", "#328464", "#5DAF8D",
            "#92DCBA", "#CDF7E2", "#E4D2AA", "#C7B08B",
            "#A08662", "#796755", "#5A4E44", "#423934",
        ],
    },
    "nes": {
        "name": "nes",
        "description": "NES 主机调色板，复古 8-bit 风格",
        "colors": [
            "#7C7C7C", "#0000FC", "#0000BC", "#4428BC",
            "#940084", "#A80020", "#A81000", "#881400",
            "#503000", "#007800", "#006800", "#005800",
            "#004058", "#000000", "#BCBCBC", "#0078F8",
            "#0058F8", "#6844FC", "#D800CC", "#E40058",
            "#F83800", "#E45C10", "#AC7C00", "#00B800",
            "#00A800", "#00A844", "#008888", "#000000",
            "#F8F8F8", "#3CBCFC", "#6888FC", "#9878F8",
            "#F878F8", "#F85898", "#F87858", "#FCA044",
            "#F8B800", "#B8F818", "#58D854", "#58F898",
            "#00E8D8", "#787878", "#FCFCFC", "#A4E4FC",
            "#B8B8F8", "#D8B8F8", "#F8B8F8", "#F8A4C0",
            "#F0D0B0", "#FCE0A8", "#F8D878", "#D8F878",
            "#B8F8B8", "#B8F8D8", "#00FCFC", "#F8D8F8",
        ],
    },
    "gameboy": {
        "name": "gameboy",
        "description": "Game Boy 4 色绿色调色板，极简复古",
        "colors": ["#0F380F", "#306230", "#8BAC0F", "#9BBC0F"],
    },
}

# Animation frame-duration presets (docs §7.2; duration_ms is a suggested value)
_TIMING_PRESETS = {
    "idle": {
        "type": "idle", "description": "待机呼吸",
        "frame_count_range": [2, 4], "duration_ms": 400,
    },
    "walk": {
        "type": "walk", "description": "行走循环",
        "frame_count_range": [4, 6], "duration_ms": 125,
    },
    "run": {
        "type": "run", "description": "跑步循环",
        "frame_count_range": [6, 8], "duration_ms": 80,
    },
    "attack_windup": {
        "type": "attack_windup", "description": "攻击蓄力",
        "frame_count_range": [1, 2], "duration_ms": 70,
    },
    "attack_hit": {
        "type": "attack_hit", "description": "攻击命中（保持更长）",
        "frame_count_range": [1, 2], "duration_ms": 160,
    },
    "attack_recover": {
        "type": "attack_recover", "description": "攻击恢复",
        "frame_count_range": [1, 2], "duration_ms": 90,
    },
    "jump_start": {
        "type": "jump_start", "description": "跳跃起跳",
        "frame_count_range": [1, 2], "duration_ms": 70,
    },
    "jump_apex": {
        "type": "jump_apex", "description": "跳跃顶点（保持）",
        "frame_count_range": [1, 1], "duration_ms": 150,
    },
    "jump_land": {
        "type": "jump_land", "description": "落地挤压",
        "frame_count_range": [1, 2], "duration_ms": 100,
    },
}

# Tileset layout templates (docs §8.2/§8.3); grid/colormap can be rewritten as-is into a
# paint_grid grid file
_TILESET_TEMPLATES = {
    "grass_dirt_16x16": {
        "name": "grass_dirt_16x16",
        "description": "草地+泥土瓦片（16x16，含中心/边缘块）",
        "tile_size": 16,
        "grid": (
            "GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGDDDDDDDDGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
        ),
        "colormap": "G=#4A7C20,D=#8B5A2B,.=transparent",
    },
    "dungeon_16x16": {
        "name": "dungeon_16x16",
        "description": "地牢石墙瓦片（16x16）",
        "tile_size": 16,
        "grid": (
            "SSSSSSSSSSSSSSSS"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/S..............S"
            "/SSSSSSSSSSSSSSSS"
        ),
        "colormap": "S=#5C5C5C,.=transparent",
    },
    "water_grass_16x16": {
        "name": "water_grass_16x16",
        "description": "水面+草地过渡瓦片（16x16）",
        "tile_size": 16,
        "grid": (
            "WWWWWWWWWWWWWWWW"
            "/WWWWWWWWWWWWWWWW"
            "/WWWWWWWWWWWWWWWW"
            "/WWWWWWWWWWWWWWWW"
            "/WWWWWWWWWWWWWWWW"
            "/WWWWWWGGGGGGGGGG"
            "/WWWWWGGGGGGGGGGG"
            "/WWWWGGGGGGGGGGGG"
            "/WWWGGGGGGGGGGGGG"
            "/WWGGGGGGGGGGGGGG"
            "/WGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
            "/GGGGGGGGGGGGGGGG"
        ),
        "colormap": "W=#2980B9,G=#4A7C20,.=transparent",
    },
}

# Standards check rules (docs §2/§4/§5/§7, read by the AI on demand)
_STANDARDS = {
    "size": {
        "category": "size",
        "rules": "尺寸应为 8/16/32/64 或 8 的倍数（docs §2.1）",
        "allowed": [8, 16, 32, 64],
        "modulo": 8,
    },
    "palette": {
        "category": "palette",
        "rules": "颜色数建议 4-32，每种主色需配阴影(×0.7)和高光(×1.3)（docs §4.1/§4.2）",
        "min_colors": 4,
        "max_colors": 32,
    },
    "timing": {
        "category": "timing",
        "rules": "不要用统一帧率，不同动作不同时长（docs §7.2）",
    },
    "pixel_art": {
        "category": "pixel_art",
        "rules": "禁止意外抗锯齿(半透明像素)；避免 jaggies(阶梯不均)；避免枕头阴影（docs §5）",
        "machine_checkable": ["semi_transparent", "isolated_pixels"],
        "visual_review": ["jaggies_shape", "pillow_shading"],
    },
}

# Every blend mode Aseprite supports
_BLEND_MODES = [
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color_dodge", "color_burn", "hard_light", "soft_light",
    "difference", "exclusion", "addition", "subtract", "divide",
    "hsl_hue", "hsl_saturation", "hsl_color", "hsl_luminosity",
]

# Animation directions
_ANI_DIRS = ["forward", "reverse", "ping_pong", "ping_pong_reverse"]

# Pixel-art drawing tips (grounded in professional game-art practice)
_PIXEL_ART_TIPS = {
    "basic_rules": [
        "使用有限调色板（4-8色），每种主色配阴影色和高光色——这是专业像素艺术的核心约束",
        "轮廓统一使用最深色，通常为黑色 #000000",
        "像素之间不要留空隙，保持填充完整",
        "斜线保持45度角，阶梯均匀（如 1-2-2-1 排列），避免锯齿",
        "线宽统一为1像素，不要出现2像素宽的线段",
        "先规划整体布局再绘制，而不是边画边想",
    ],
    "shading": [
        "光源通常设在左上方，阴影画在右下方",
        "阴影色 = 主色 RGB 各分量乘以 0.7",
        "高光色 = 主色 RGB 各分量乘以 1.3（上限255）",
        "阴影不要画太多，1-2像素宽即可，避免枕头式阴影",
        "不要只沿轮廓涂阴影——先想好光源方向，再确定阴影区域",
        "使用色相偏移：暗部偏冷色（蓝/紫），亮部偏暖色（黄/橙）",
    ],
    "outline": [
        "轮廓要连续不断裂，线宽统一",
        "把轮廓直接画进网格规划里（字符 K 通常留给轮廓色），没有单独的描边 op",
        "内轮廓（主体边缘内侧）用主色的暗化版本，不要全用黑色",
        "轮廓颜色可做色相偏移，比纯黑更有层次感",
    ],
    "symmetry": [
        "对称图形在规划网格时就要左右对齐，行内字符成对镜像，而不是画完再镜像",
        "规划时先定轴线（16x16 画布的中轴是第 8 列），逐行照着写两遍",
        "像素坐标按 x/y 双向检查，避免手工镜像时差 1 像素",
    ],
    "animation": [
        "先画关键帧（最极端姿势），再补中间帧——这是专业动画的标准流程",
        "每帧只做小幅修改（1-3像素位移），保持动作连贯",
        "行走循环：腿臂交替摆动，身体微微上下起伏",
        "闪烁效果：缩放或明暗交替变化",
        "用 inspect 的 frame 参数逐帧对比，参考前后帧确保动作连贯",
    ],
    "workflow": [
        "专业流程：草图 → 线稿 → 平涂底色 → 阴影/高光 → 描边 → 导出",
        "先把底色和高光阴影全部写进网格规划，再用 paint_grid 一次平涂",
        "描边同样写进网格规划（轮廓色占一个字符），不靠事后处理",
        "最后用 draw_pixel 做少量像素级修正",
        "每步都用 inspect 检查效果（scale 放大便于观察）",
    ],
}

# Grid layouts for common pixel-art subjects (the LLM can follow these patterns)
_SPRITE_PATTERNS = {
    "mushroom_16x16": {
        "description": "蘑菇（16x16）",
        "grid": (
            ".....KKKKKK....."
            "/....KRRRRRRK...."
            "/...KRRWWWWRRK..."
            "/...KRWWWWWWRK..."
            "/...KRRWWWWRRK..."
            "/....KRRRRRRK...."
            "/.....KKKKKK....."
            "/.....KSSSSK....."
            "/.....KSSSSK....."
            "/.....KKKKKK....."
        ),
        "colormap": "K=#000000,R=#E74C3C,W=#FFFFFF,S=#F5DEB3,.=transparent",
    },
    "heart_16x16": {
        "description": "心形（16x16）",
        "grid": (
            "................"
            "/..RR....RR....."
            "/.RWWR..RWWR...."
            "/RWWWWRWWWWR...."
            "/RWWWWWWWWWWR..."
            "/RWWWWWWWWWWR..."
            "/.RWWWWWWWWR...."
            "/..RWWWWWWR....."
            "/...RWWWWR......"
            "/....RWWR......."
            "/.....RR........"
            "/................"
        ),
        "colormap": "R=#E74C3C,W=#FFB3B3,.=transparent",
    },
    "gem_16x16": {
        "description": "宝石（16x16）",
        "grid": (
            "................"
            "/.....KKKK......"
            "/....KBBBWK....."
            "/...KBBWWWBK...."
            "/..KBWWWWWBWK..."
            "/..KBWWWWWBWK..."
            "/...KBBWWWBK...."
            "/....KBBBWK....."
            "/.....KKKK......"
            "/................"
        ),
        "colormap": "K=#000000,B=#29ADFF,W=#A9E2FF,.=transparent",
    },
}


def register_resources(mcp, session_manager: SessionManager):
    """Register the MCP resources.

    Args:
        mcp: FastMCP instance
        session_manager: the session manager
    """

    @mcp.resource("aseprite://sessions")
    def list_sessions() -> str:
        """List every active drawing session."""
        return json.dumps(session_manager.list_sessions())

    @mcp.resource("aseprite://palette/default")
    def get_default_palette() -> str:
        """Return the default pixel-art palette (16 colors)."""
        return json.dumps({"colors": _DEFAULT_PALETTE})

    @mcp.resource("aseprite://palette/presets")
    def list_palette_presets() -> str:
        """Return the names of the available preset palettes (docs §4.3)."""
        return json.dumps({"presets": list(_PRESET_PALETTES.keys())})

    @mcp.resource("aseprite://palette/presets/{name}")
    def get_palette_preset(name: str) -> str:
        """Return the full color values of one preset palette.

        Available: db16, db32, aap64, nes, gameboy
        """
        preset = _PRESET_PALETTES.get(name)
        if not preset:
            return json.dumps({"error": f"Preset not found: {name}"})
        return json.dumps(preset)

    @mcp.resource("aseprite://timing/presets")
    def list_timing_presets() -> str:
        """Return the animation frame-duration preset types (docs §7.2)."""
        return json.dumps({"presets": list(_TIMING_PRESETS.keys())})

    @mcp.resource("aseprite://timing/presets/{type}")
    def get_timing_preset(type: str) -> str:
        """Return the frame-duration preset for one animation type.

        Available: idle, walk, run, attack_windup, attack_hit, attack_recover,
                   jump_start, jump_apex, jump_land
        """
        preset = _TIMING_PRESETS.get(type)
        if not preset:
            return json.dumps({"error": f"Timing preset not found: {type}"})
        return json.dumps(preset)

    @mcp.resource("aseprite://canvas/{session_id}/info")
    def get_canvas_info_resource(session_id: str) -> str:
        """Return the canvas metadata of one session."""
        info = session_manager.get_canvas_info(session_id)
        return json.dumps(info)

    @mcp.resource("aseprite://blendmodes")
    def list_blend_modes() -> str:
        """Return every blend mode Aseprite supports."""
        return json.dumps({"blend_modes": _BLEND_MODES})

    @mcp.resource("aseprite://anidirs")
    def list_ani_dirs() -> str:
        """Return every animation direction Aseprite supports."""
        return json.dumps({"ani_dirs": _ANI_DIRS})

    @mcp.resource("aseprite://tips/{category}")
    def get_pixel_art_tips(category: str) -> str:
        """Return pixel-art drawing tips.

        Available categories: basic_rules, shading, outline, symmetry, animation, workflow
        """
        tips = _PIXEL_ART_TIPS.get(category, [])
        return json.dumps({"category": category, "tips": tips})

    @mcp.resource("aseprite://patterns")
    def list_sprite_patterns() -> str:
        """Return the available sprite grid-layout reference templates."""
        patterns = {
            name: {"description": p["description"]}
            for name, p in _SPRITE_PATTERNS.items()
        }
        return json.dumps({"patterns": patterns})

    @mcp.resource("aseprite://patterns/{name}")
    def get_sprite_pattern(name: str) -> str:
        """Return the full grid layout for one sprite (grid rows + colormap char->color).

        Getting it onto the canvas goes through paint_grid: split colormap into a Lua
        palette table, split grid on "/" into a rows array, write them into a .lua file
        returning that table, then load it with apply_operations'
        {"op": "paint_grid", "path": "<absolute path>"}.
        A paint_grid file inside the work directory runs as-is; a path pointing outside
        needs confirmed=true.
        """
        pattern = _SPRITE_PATTERNS.get(name)
        if not pattern:
            return json.dumps({"error": f"Pattern not found: {name}"})
        return json.dumps(pattern)

    @mcp.resource("aseprite://tileset/templates")
    def list_tileset_templates() -> str:
        """Return the available tileset layout templates (docs §8.2)."""
        templates = {
            name: {"description": t["description"], "tile_size": t["tile_size"]}
            for name, t in _TILESET_TEMPLATES.items()
        }
        return json.dumps({"templates": templates})

    @mcp.resource("aseprite://tileset/templates/{name}")
    def get_tileset_template(name: str) -> str:
        """Return the full grid/colormap of one tileset template.

        Like aseprite://patterns/{name} it has to be rewritten into a paint_grid grid
        file; use paint_grid's x/y to place the single tile at the matching cell on the
        canvas.

        Available: grass_dirt_16x16, dungeon_16x16, water_grass_16x16
        """
        template = _TILESET_TEMPLATES.get(name)
        if not template:
            return json.dumps({"error": f"Template not found: {name}"})
        return json.dumps(template)

    @mcp.resource("aseprite://standards/{category}")
    def get_standards(category: str) -> str:
        """Return the standards rules for one category (docs §2/§4/§5/§7).

        Available: size, palette, timing, pixel_art
        """
        std = _STANDARDS.get(category)
        if not std:
            return json.dumps({"error": f"Standards category not found: {category}"})
        return json.dumps(std)
