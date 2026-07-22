"""MCP Resources：只读数据源。

提供会话列表、调色板、画布信息、混合模式列表等只读数据。
"""

import json

from src.session import SessionManager


# Aseprite 默认调色板（经典 16 色像素艺术调色板）
_DEFAULT_PALETTE = [
    "#000000", "#1D2B53", "#7E2553", "#008751",
    "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
    "#FF004D", "#FFA300", "#FFEC27", "#00E436",
    "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA",
]

# 预设调色板库（docs §4.3，色值采用公开标准）
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
        "description": "AAP-64，现代像素艺术 64 色标准",
        "colors": [
            "#060608", "#101218", "#1B1F2A", "#2B2F3A",
            "#3F434F", "#545965", "#6D7280", "#8A8F9D",
            "#A7ADB9", "#C4CACE", "#E1E3E4", "#FFFFFF",
            "#330000", "#660000", "#990000", "#CC0000",
            "#FE0000", "#FE6600", "#FE9900", "#FECC00",
            "#FFFF00", "#CCFF00", "#99FF00", "#66FF00",
            "#33FF00", "#00FE00", "#00CC00", "#009900",
            "#006600", "#003300", "#003366", "#006699",
            "#0099CC", "#00CCFF", "#00FFFF", "#33CCFF",
            "#6699FF", "#6633FF", "#6600CC", "#330099",
            "#330066", "#660099", "#9933FF", "#9966FF",
            "#CC99FF", "#FFCCFF", "#FF99CC", "#FF6699",
            "#FF3366", "#FF0033", "#CC0066", "#990066",
            "#663366", "#4D224D", "#3D2233", "#2D1122",
            "#6D6D6D", "#999999", "#B3B3B3", "#CCCCCC",
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

# Aseprite 支持的所有混合模式
_BLEND_MODES = [
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color_dodge", "color_burn", "hard_light", "soft_light",
    "difference", "exclusion", "addition", "subtract", "divide",
    "hsl_hue", "hsl_saturation", "hsl_color", "hsl_luminosity",
]

# 动画方向
_ANI_DIRS = ["forward", "reverse", "ping_pong", "ping_pong_reverse"]

# 像素艺术绘制技巧参考（基于专业游戏美术实践）
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
        "可用 add_outline 工具自动生成描边",
        "内轮廓（主体边缘内侧）用主色的暗化版本，不要全用黑色",
        "轮廓颜色可做色相偏移，比纯黑更有层次感",
    ],
    "symmetry": [
        "对称图形只画一半，用 mirror_half 镜像复制",
        "水平镜像用 axis=x，垂直镜像用 axis=y",
        "position 参数设为画布宽度/2（如16x16画布 position=8）",
    ],
    "animation": [
        "先画关键帧（最极端姿势），再补中间帧——这是专业动画的标准流程",
        "每帧只做小幅修改（1-3像素位移），保持动作连贯",
        "行走循环：腿臂交替摆动，身体微微上下起伏",
        "闪烁效果：缩放或明暗交替变化",
        "使用洋葱皮（onion skin）思路：参考前后帧确保动作连贯",
    ],
    "workflow": [
        "专业流程：草图 → 线稿 → 平涂底色 → 阴影/高光 → 描边 → 导出",
        "先用 draw_from_grid 一次性平涂所有底色和高光阴影",
        "再用 add_outline 自动描边",
        "最后用 draw_pixel 做少量像素级修正",
        "每步都用 get_canvas_preview 检查效果",
    ],
}

# 常见像素角色的网格布局参考（LLM 可参考这些模式）
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
    """注册 MCP Resources。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
    """

    @mcp.resource("aseprite://sessions")
    def list_sessions() -> str:
        """列出当前所有活跃的绘制会话。"""
        return json.dumps(session_manager.list_sessions())

    @mcp.resource("aseprite://palette/default")
    def get_default_palette() -> str:
        """返回默认像素艺术调色板（16 色）。"""
        return json.dumps({"colors": _DEFAULT_PALETTE})

    @mcp.resource("aseprite://palette/presets")
    def list_palette_presets() -> str:
        """返回可用的预设调色板名称列表（docs §4.3）。"""
        return json.dumps({"presets": list(_PRESET_PALETTES.keys())})

    @mcp.resource("aseprite://palette/presets/{name}")
    def get_palette_preset(name: str) -> str:
        """返回指定预设调色板的完整色值。

        可用: db16, db32, aap64, nes, gameboy
        """
        preset = _PRESET_PALETTES.get(name)
        if not preset:
            return json.dumps({"error": f"Preset not found: {name}"})
        return json.dumps(preset)

    @mcp.resource("aseprite://canvas/{session_id}/info")
    def get_canvas_info_resource(session_id: str) -> str:
        """获取指定会话的画布元数据。"""
        info = session_manager.get_canvas_info(session_id)
        return json.dumps(info)

    @mcp.resource("aseprite://blendmodes")
    def list_blend_modes() -> str:
        """返回 Aseprite 支持的所有混合模式列表。"""
        return json.dumps({"blend_modes": _BLEND_MODES})

    @mcp.resource("aseprite://anidirs")
    def list_ani_dirs() -> str:
        """返回 Aseprite 支持的所有动画方向列表。"""
        return json.dumps({"ani_dirs": _ANI_DIRS})

    @mcp.resource("aseprite://tips/{category}")
    def get_pixel_art_tips(category: str) -> str:
        """获取像素艺术绘制技巧。

        可用分类: basic_rules, shading, outline, symmetry, animation, workflow
        """
        tips = _PIXEL_ART_TIPS.get(category, [])
        return json.dumps({"category": category, "tips": tips})

    @mcp.resource("aseprite://patterns")
    def list_sprite_patterns() -> str:
        """返回可用的精灵网格布局参考模板列表。"""
        patterns = {
            name: {"description": p["description"]}
            for name, p in _SPRITE_PATTERNS.items()
        }
        return json.dumps({"patterns": patterns})

    @mcp.resource("aseprite://patterns/{name}")
    def get_sprite_pattern(name: str) -> str:
        """获取指定精灵的完整网格布局参考（grid 和 colormap）。

        可直接将返回的 grid 和 colormap 传入 draw_from_grid 工具使用。
        """
        pattern = _SPRITE_PATTERNS.get(name)
        if not pattern:
            return json.dumps({"error": f"Pattern not found: {name}"})
        return json.dumps(pattern)
