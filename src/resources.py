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

# Aseprite 支持的所有混合模式
_BLEND_MODES = [
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color_dodge", "color_burn", "hard_light", "soft_light",
    "difference", "exclusion", "addition", "subtract", "divide",
    "hsl_hue", "hsl_saturation", "hsl_color", "hsl_luminosity",
]

# 动画方向
_ANI_DIRS = ["forward", "reverse", "ping_pong", "ping_pong_reverse"]

# 像素艺术绘制技巧参考
_PIXEL_ART_TIPS = {
    "basic_rules": [
        "使用有限调色板（4-8色），每种主色配阴影色和高光色",
        "轮廓统一使用最深色，通常为黑色 #000000",
        "像素之间不要留空隙，保持填充完整",
        "斜线保持45度角，阶梯均匀避免锯齿",
    ],
    "shading": [
        "光源通常设在左上方，阴影画在右下方",
        "阴影色 = 主色 RGB 各分量乘以 0.7",
        "高光色 = 主色 RGB 各分量乘以 1.3（上限255）",
        "阴影不要画太多，1-2像素宽即可",
    ],
    "outline": [
        "先画轮廓再填充内部颜色",
        "轮廓要连续不断裂",
        "可用 add_outline 工具自动生成描边",
        "内轮廓（在主体边缘内侧）用主色的暗化版本",
    ],
    "symmetry": [
        "对称图形只画一半，用 mirror_half 镜像复制",
        "水平镜像用 axis=x，垂直镜像用 axis=y",
        "position 参数设为画布宽度/2（如16x16画布 position=8）",
    ],
    "animation": [
        "每帧只做小幅修改（1-3像素位移），保持动作连贯",
        "先画关键帧（最极端姿势），再补中间帧",
        "行走循环：腿臂交替摆动，身体微微上下起伏",
        "闪烁效果：缩放或明暗交替变化",
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

        可用分类: basic_rules, shading, outline, symmetry, animation
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
