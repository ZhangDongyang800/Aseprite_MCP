# Aseprite MCP 改进实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 `docs/Aseprite游戏素材制作流程与规范.md` 为 Aseprite MCP 补齐调色板增强、动画辅助、Tileset 工具集、质量检查四个方向的能力，并通过批量原语将 MCP 调用次数最小化。

**Architecture:** 沿用现有 FastMCP + subprocess + Lua 脚本模式（零侵入）。规范知识沉淀为 MCP Resources；新增工具侧重"应用预设 / 执行检查 / 批量原语"。纯计算工具（derive_shading_palette）在 Python 层完成，不起 Lua。

**Tech Stack:** Python 3.10+ / FastMCP 2.0+ / Aseprite CLI + Lua / pytest

**Spec:** `docs/specs/2026-07-22-mcp-improvement-design.md`

---

## 文件结构

**新建文件：**
- `scripts/apply_palette.lua` — 整板替换调色板（apply_preset_palette 用）
- `scripts/append_palette.lua` — 批量追加调色板颜色（append_palette_colors / derive_shading_palette 用）
- `scripts/set_frame_durations.lua` — 批量设置帧时长（apply_timing_preset 用）
- `scripts/export_onion_skin.lua` — 洋葱皮叠加预览
- `scripts/draw_animation_frames.lua` — 批量绘制多帧（draw_animation_frames 用）
- `scripts/create_tileset.lua` — 创建瓦片画布并设网格
- `scripts/export_tiled.lua` — 平铺拼接预览
- `scripts/export_silhouette.lua` — 剪影导出
- `scripts/check_standards.lua` — 画布规范检查
- `src/tools/tileset_tools.py` — Tileset 工具注册
- `src/tools/quality_tools.py` — 质量检查工具注册
- `tests/test_palette_preset_tools.py` — 调色板增强测试
- `tests/test_animation_preset_tools.py` — 动画辅助测试
- `tests/test_tileset_tools.py` — Tileset 工具测试
- `tests/test_quality_tools.py` — 质量检查测试

**修改文件：**
- `src/resources.py` — 新增 7 个 Resource URI + 预设数据字典
- `src/tools/palette_tools.py` — 注册 apply_preset_palette / derive_shading_palette / append_palette_colors
- `src/tools/animation_tools.py` — 注册 apply_timing_preset / export_onion_skin_preview / draw_animation_frames
- `src/tools/inspect_tools.py` — 现有工具描述补 `⚠️ 勿循环` 提示（draw_pixel 等）
- `src/tools/draw_tools.py` — 现有工具描述补 `⚠️ 勿循环` 提示
- `server.py` — 注册 tileset_tools / quality_tools
- `src/prompts.py` — 新增 create_tileset_prompt + 现有 prompt 补调用基准
- `README.md` / `README_EN.md` — 工具表 38→48

**既有模式约定（所有新代码遵循）：**
- 工具模块：`register_xxx_tools(mcp, session_manager, runner)` 函数 + 内部 `_run_xxx_script(session_id, script_name, params)` 公共逻辑
- 只读工具：`@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})`
- 返回图片工具：`from fastmcp.utilities.types import Image`，`Image(path=str(png_path))`
- Lua：`app.params["x"]` 取参，`app.open(file)`，`sprite:saveAs(file)`，`print("OK: ...")` / `print('{"error":...}')`
- 返回 JSON 的 Lua：用 `string.format` 拼 JSON
- 测试：`setup` fixture mock 依赖 + `capture_tool` 捕获工具函数到 `tools` 字典

---

## 阶段一：调色板增强

### Task 1: 调色板预设 Resources 数据

**Files:**
- Modify: `src/resources.py`

- [ ] **Step 1: 在 `src/resources.py` 顶部数据区新增预设调色板字典**

在 `_DEFAULT_PALETTE` 定义之后插入（色值采用公开标准 DawnBringer 系列 / AAP-64 / NES / Game Boy）：

```python
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
```

- [ ] **Step 2: 在 `register_resources` 内新增两个预设 Resource**

在 `get_default_palette` 之后插入：

```python
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
```

- [ ] **Step 3: 提交**

```bash
git add src/resources.py
git commit -m "feat: 新增调色板预设 Resources（DB16/DB32/AAP64/NES/GB）"
```

---

### Task 2: apply_palette.lua + append_palette.lua 脚本

**Files:**
- Create: `scripts/apply_palette.lua`
- Create: `scripts/append_palette.lua`

- [ ] **Step 1: 创建 `scripts/apply_palette.lua`**（整板替换，apply_preset_palette 用）

```lua
-- apply_palette.lua：整板替换调色板为指定颜色序列
-- 参数: file, colors (逗号分隔的 #RRGGBB 列表)
-- 行为: 调整调色板大小为 colors 数量，逐色写入（覆盖原调色板）
local file = app.params["file"]
local colors_str = app.params["colors"]

if not file or not colors_str then
    print("ERROR: file and colors are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

local pal = sprite.palettes[1]
if not pal then
    print("ERROR: no palette found")
    return
end

-- 解析颜色列表
local colors = {}
for hex in colors_str:gmatch("[^,]+") do
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    table.insert(colors, {r=r, g=g, b=b})
end

-- 调整调色板大小并写入（整板替换）
pal:resize(#colors)
for i, c in ipairs(colors) do
    pal:setColor(i - 1, Color{r=c.r, g=c.g, b=c.b, a=255})
end

sprite:saveAs(file)
print("OK: applied palette with " .. #colors .. " colors")
```

- [ ] **Step 2: 创建 `scripts/append_palette.lua`**（尾部追加，append_palette_colors 用）

```lua
-- append_palette.lua：批量追加颜色到调色板末尾
-- 参数: file, colors (逗号分隔的 #RRGGBB 列表)
-- 行为: 在现有调色板末尾追加颜色，不覆盖已有颜色
local file = app.params["file"]
local colors_str = app.params["colors"]

if not file or not colors_str then
    print("ERROR: file and colors are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

local pal = sprite.palettes[1]
if not pal then
    print("ERROR: no palette found")
    return
end

-- 计算当前调色板大小，追加颜色
local start_index = #pal
local count = 0
for hex in colors_str:gmatch("[^,]+") do
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    -- addColor 追加到末尾
    pal:addColor(Color{r=r, g=g, b=b, a=255})
    count = count + 1
end

sprite:saveAs(file)
print("OK: appended " .. count .. " colors to palette (now " .. #pal .. " total)")
```

- [ ] **Step 3: 提交**

```bash
git add scripts/apply_palette.lua scripts/append_palette.lua
git commit -m "feat: 新增 apply_palette/append_palette Lua 脚本"
```

---

### Task 3: apply_preset_palette + append_palette_colors + derive_shading_palette 工具

**Files:**
- Modify: `src/tools/palette_tools.py`
- Test: `tests/test_palette_preset_tools.py`

- [ ] **Step 1: 写失败测试 `tests/test_palette_preset_tools.py`**

```python
"""调色板增强工具测试：apply_preset_palette / append_palette_colors / derive_shading_palette。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.palette_tools import register_palette_tools


@pytest.fixture
def setup():
    """mock 依赖并捕获工具函数。"""
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool
    register_palette_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_apply_preset_palette_calls_apply_palette_script(setup):
    """apply_preset_palette 应调用 apply_palette.lua 并传入预设色值。"""
    tools, session_manager, runner = setup
    runner.run_script.return_value = {
        "success": True, "stdout": "OK", "stderr": ""
    }

    result = tools["apply_preset_palette"](session_id="s1", preset_name="gameboy")

    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "apply_palette.lua"
    # gameboy 4 色，应包含 #0F380F
    assert "#0F380F" in call_args[0][1]["colors"]


def test_apply_preset_palette_rejects_unknown_preset(setup):
    """未知预设名应返回错误。"""
    tools, _, _ = setup
    result = tools["apply_preset_palette"](session_id="s1", preset_name="unknown")
    assert result["success"] is False
    assert "unknown" in result["error"]


def test_append_palette_colors_calls_append_script(setup):
    """append_palette_colors 应调用 append_palette.lua。"""
    tools, _, _ = setup
    result = tools["append_palette_colors"](
        session_id="s1", colors="#FF0000,#00FF00,#0000FF"
    )
    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "append_palette.lua"
    assert call_args[0][1]["colors"] == "#FF0000,#00FF00,#0000FF"


def test_derive_shading_palette_returns_five_shades(setup):
    """derive_shading_palette 默认返回 5 阶配色。"""
    tools, _, _ = setup
    result = tools["derive_shading_palette"](base_color="#808080", apply_to_palette=False)
    assert result["success"] is True
    assert len(result["colors_hex"]) == 5
    assert result["colors_hex"][3] == "#000000"  # outline


def test_derive_shading_palette_highlight_is_brighter(setup):
    """高光色应比主色亮。"""
    tools, _, _ = setup
    result = tools["derive_shading_palette"](base_color="#808080", apply_to_palette=False)
    colors = result["colors_hex"]
    # colors[0]=highlight, colors[1]=base
    assert int(colors[0][1:3], 16) > int(colors[1][1:3], 16)


def test_derive_shading_palette_hue_shift_off(setup):
    """hue_shift=false 时关闭色相偏移（纯亮度缩放）。"""
    tools, _, _ = setup
    result = tools["derive_shading_palette"](
        base_color="#808080", hue_shift=False, apply_to_palette=False
    )
    # 关闭色相偏移后，灰色的高光三通道应相等
    hl = result["colors_hex"][0]
    r, g, b = int(hl[1:3], 16), int(hl[3:5], 16), int(hl[5:7], 16)
    assert r == g == b


def test_derive_shading_palette_apply_calls_append(setup):
    """apply_to_palette=true 时应调用 append_palette.lua 追加。"""
    tools, _, runner = setup
    result = tools["derive_shading_palette"](base_color="#808080", apply_to_palette=True, session_id="s1")
    assert result["success"] is True
    assert runner.run_script.called
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "append_palette.lua"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_palette_preset_tools.py -v`
Expected: FAIL（工具未定义）

- [ ] **Step 3: 在 `src/tools/palette_tools.py` 末尾（`load_palette` 工具之后）新增三个工具**

先在文件顶部 import 区补充：
```python
from src.resources import _PRESET_PALETTES
```

在 `register_palette_tools` 函数内、`load_palette` 工具定义之后追加：

```python
    # ===== 调色板增强工具（docs §4）=====

    # 预设调色板名称白名单
    _PRESET_NAMES = set(_PRESET_PALETTES.keys())

    @mcp.tool
    def apply_preset_palette(session_id: str, preset_name: str) -> dict:
        """★批量★ 应用内置预设调色板到画布（整板替换）。

        一次调用写入整个预设调色板，替代 N 次 set_palette_color。
        可用预设: db16(16色), db32(32色), aap64(64色), nes(NES复古), gameboy(4色绿)。

        Args:
            session_id: 会话 ID
            preset_name: 预设名（db16/db32/aap64/nes/gameboy）
        """
        if preset_name not in _PRESET_NAMES:
            return {
                "success": False,
                "error": f"Unknown preset: {preset_name}. Available: {sorted(_PRESET_NAMES)}",
            }
        colors = _PRESET_PALETTES[preset_name]["colors"]
        return _run_palette_script(session_id, "apply_palette.lua", {
            "colors": ",".join(colors),
        })

    @mcp.tool
    def append_palette_colors(session_id: str, colors: str) -> dict:
        """★批量★ 一次追加多个颜色到调色板末尾，替代 N 次 set_palette_color 循环。

        ⚠️ 不要循环调用 set_palette_color，N 个颜色请用本工具一次完成。

        Args:
            session_id: 会话 ID
            colors: 逗号分隔的 #RRGGBB 列表，如 "#FF0000,#00FF00,#0000FF"
        """
        return _run_palette_script(session_id, "append_palette.lua", {
            "colors": colors,
        })

    @mcp.tool
    def derive_shading_palette(
        base_color: str,
        shades: int = 5,
        hue_shift: bool = True,
        apply_to_palette: bool = True,
        session_id: str = None,
    ) -> dict:
        """按 docs §3.4/§4.4 公式从主色派生专业三阶配色（高光/主色/阴影/深阴影/轮廓）。

        色相偏移：暗部偏冷(蓝)、亮部偏暖(黄)，避免业余的"发灰"配色。
        默认 apply_to_palette=true，自动追加到调色板（1 次 append_palette_colors 调用）。

        Args:
            base_color: 主色 #RRGGBB
            shades: 返回色阶数（默认 5）
            hue_shift: 是否启用色相偏移（默认 true，关闭则纯亮度缩放）
            apply_to_palette: 是否追加到调色板（默认 true，需提供 session_id）
            session_id: 会话 ID（apply_to_palette=true 时必填）
        """
        color = validate_color(base_color)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        # 色相偏移强度
        k = 20 if hue_shift else 0

        def clamp(v):
            return max(0, min(255, round(v)))

        # 高光：亮部偏暖（R 增幅大，B 降），×1.3
        highlight = f"#{clamp(r*1.3 + k):02X}{clamp(g*1.3 + k*0.3):02X}{clamp(b*1.3 - k):02X}"
        base = f"#{r:02X}{g:02X}{b:02X}"
        # 阴影：暗部偏冷（B 增幅大，R 降），×0.7
        shadow = f"#{clamp(r*0.7 - k*0.3):02X}{clamp(g*0.7):02X}{clamp(b*0.7 + k):02X}"
        # 深阴影：×0.5
        deep_shadow = f"#{clamp(r*0.5):02X}{clamp(g*0.5):02X}{clamp(b*0.5 + k*0.5):02X}"
        outline = "#000000"

        all_shades = [highlight, base, shadow, deep_shadow, outline][:shades]

        if apply_to_palette:
            if not session_id:
                return {"success": False, "error": "session_id is required when apply_to_palette=true"}
            # 复用 append_palette_colors 一次性追加
            append_result = append_palette_colors(session_id, ",".join(all_shades))
            if not append_result["success"]:
                return append_result

        return {"success": True, "colors_hex": all_shades}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_palette_preset_tools.py -v`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add src/tools/palette_tools.py tests/test_palette_preset_tools.py
git commit -m "feat: 调色板增强工具（apply_preset_palette/append_palette_colors/derive_shading_palette）"
```

---

## 阶段二：动画辅助增强

### Task 4: 帧时长预设 Resources

**Files:**
- Modify: `src/resources.py`

- [ ] **Step 1: 在 `src/resources.py` 新增帧时长预设字典**

在 `_PRESET_PALETTES` 之后插入（数据来自 docs §7.2）：

```python
# 动画帧时长预设（docs §7.2，duration_ms 为建议值）
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
```

- [ ] **Step 2: 在 `register_resources` 内新增两个 timing Resource**

```python
    @mcp.resource("aseprite://timing/presets")
    def list_timing_presets() -> str:
        """返回动画帧时长预设类型列表（docs §7.2）。"""
        return json.dumps({"presets": list(_TIMING_PRESETS.keys())})

    @mcp.resource("aseprite://timing/presets/{type}")
    def get_timing_preset(type: str) -> str:
        """返回指定动画类型的帧时长预设。

        可用: idle, walk, run, attack_windup, attack_hit, attack_recover,
              jump_start, jump_apex, jump_land
        """
        preset = _TIMING_PRESETS.get(type)
        if not preset:
            return json.dumps({"error": f"Timing preset not found: {type}"})
        return json.dumps(preset)
```

- [ ] **Step 3: 提交**

```bash
git add src/resources.py
git commit -m "feat: 新增帧时长预设 Resources（docs §7.2）"
```

---

### Task 5: set_frame_durations.lua + draw_animation_frames.lua + export_onion_skin.lua

**Files:**
- Create: `scripts/set_frame_durations.lua`
- Create: `scripts/draw_animation_frames.lua`
- Create: `scripts/export_onion_skin.lua`

- [ ] **Step 1: 创建 `scripts/set_frame_durations.lua`**

```lua
-- set_frame_durations.lua：批量设置所有帧的时长
-- 参数: file, durations (逗号分隔的毫秒数，如 "125,125,125,125")
local file = app.params["file"]
local durations_str = app.params["durations"]

if not file or not durations_str then
    print("ERROR: file and durations are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 解析时长列表
local durations = {}
for d in durations_str:gmatch("[^,]+") do
    table.insert(durations, tonumber(d))
end

-- 逐帧设置时长（毫秒转秒）
local count = 0
for i, dur in ipairs(durations) do
    if sprite.frames[i] then
        sprite.frames[i].duration = dur / 1000.0
        count = count + 1
    end
end

sprite:saveAs(file)
print("OK: set durations for " .. count .. " frames")
```

- [ ] **Step 2: 创建 `scripts/draw_animation_frames.lua`**（批量绘制多帧，核心调用优化）

```lua
-- draw_animation_frames.lua：一次绘制多帧动画
-- 参数: file, grids (用 | 分隔每帧，帧内行用 / 分隔), colormap, mode (copy/blank), layer
local file = app.params["file"]
local grids_str = app.params["grids"]
local colormap_str = app.params["colormap"]
local mode = app.params["mode"] or "copy"
local layer_idx = tonumber(app.params["layer"] or "1")

if not file or not grids_str or not colormap_str then
    print("ERROR: file, grids, colormap are required")
    return
end

-- 解析颜色映射表
local colormap = {}
for entry in colormap_str:gmatch("[^,]+") do
    local char, color = entry:match("^(.)=(.+)$")
    if char then
        if color == "transparent" or color == "none" then
            colormap[char] = nil
        else
            local r = tonumber(color:sub(2, 3), 16)
            local g = tonumber(color:sub(4, 5), 16)
            local b = tonumber(color:sub(6, 7), 16)
            colormap[char] = app.pixelColor.rgba(r, g, b, 255)
        end
    end
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

local target_layer = sprite.layers[layer_idx]
if not target_layer then
    print("ERROR: layer not found: " .. layer_idx)
    return
end

-- 按 | 分割每帧的 grid
local frames_grid = {}
for frame_grid in grids_str:gmatch("[^|]+") do
    table.insert(frames_grid, frame_grid)
end

local frames_drawn = 0

-- 第 1 帧使用已有帧，第 2 帧起新建帧
local start_frame = 2
for fi = 1, #frames_grid do
    local frame_idx
    if fi == 1 then
        -- 第 1 帧使用现有第 1 帧
        frame_idx = 1
    else
        -- 新建帧
        local new_frame = sprite:newFrame(#sprite.frames + 1)
        frame_idx = new_frame.frameNumber
        -- copy 模式：复制上一帧的 cel
        if mode == "copy" then
            local prev_cel = target_layer:cel(frame_idx - 1)
            if prev_cel then
                local new_cel = sprite:newCel(target_layer, frame_idx, prev_cel.image, prev_cel.position)
            end
        end
    end

    -- 获取或创建当前帧的 cel
    local cel = target_layer:cel(frame_idx)
    if not cel then
        cel = sprite:newCel(target_layer, frame_idx)
    end
    local image = cel.image

    -- 解析本帧 grid 并绘制
    local row_idx = 0
    for row in frames_grid[fi]:gmatch("[^/]+") do
        local col_idx = 0
        for char in row:gmatch(".") do
            local color = colormap[char]
            if color then
                image:drawPixel(col_idx, row_idx, color)
            end
            col_idx = col_idx + 1
        end
        row_idx = row_idx + 1
    end
    frames_drawn = frames_drawn + 1
end

sprite:saveAs(file)
print("OK: drew " .. frames_drawn .. " frames")
```

- [ ] **Step 3: 创建 `scripts/export_onion_skin.lua`**（洋葱皮叠加预览，导出 PNG）

```lua
-- export_onion_skin.lua：导出洋葱皮叠加预览 PNG
-- 参数: file, output (PNG 路径), frame (中心帧号 1-indexed), scale
-- 行为: 前一帧(红半透明) + 当前帧(原色) + 后一帧(蓝半透明) 叠加导出
local file = app.params["file"]
local output = app.params["output"]
local frame_idx = tonumber(app.params["frame"] or "1")
local scale = tonumber(app.params["scale"] or "1")

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

local w = sprite.width
local h = sprite.height

-- 创建叠加用的 Image（RGBA）
local result = Image(w, h, sprite.colorMode)
result:clear()

-- 工具函数：把某帧叠加到 result，tint 为 {r,g,b,a} 色调
local function overlay(frame_no, tr, tg, tb, ta)
    if not sprite.frames[frame_no] then return end
    local layer = sprite.layers[1]
    local cel = layer:cel(frame_no)
    if not cel or not cel.image then return end
    local img = cel.image
    for it in img:pixels() do
        local pc = it()
        local a = app.pixelColor.rgbaA(pc)
        if a > 0 then
            -- 取原图 rgb，应用色调与 alpha
            local r = app.pixelColor.rgbaR(pc)
            local g = app.pixelColor.rgbaG(pc)
            local b = app.pixelColor.rgbaB(pc)
            -- 色调混合：与 tint 色按 ta 混合
            local mr = math.floor(r * (255 - ta) / 255 + tr * ta / 255)
            local mg = math.floor(g * (255 - ta) / 255 + tg * ta / 255)
            local mb = math.floor(b * (255 - ta) / 255 + tb * ta / 255)
            result:drawPixel(it.x, it.y, app.pixelColor.rgba(mr, mg, mb, 255))
        end
    end
end

-- 前一帧（红色半透明，ta=100）
overlay(frame_idx - 1, 255, 0, 0, 100)
-- 当前帧（原色，ta=0 即不调色）
overlay(frame_idx, 0, 0, 0, 0)
-- 后一帧（蓝色半透明，ta=100）
overlay(frame_idx + 1, 0, 0, 255, 100)

-- 导出叠加图（用临时 sprite 保存）
local tmp_sprite = Sprite(w, h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(result)
if scale > 1 then
    tmp_sprite:resize(w * scale, h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print("OK: exported onion skin preview to " .. output)
```

- [ ] **Step 4: 提交**

```bash
git add scripts/set_frame_durations.lua scripts/draw_animation_frames.lua scripts/export_onion_skin.lua
git commit -m "feat: 新增 set_frame_durations/draw_animation_frames/export_onion_skin Lua 脚本"
```

---

### Task 6: apply_timing_preset + export_onion_skin_preview + draw_animation_frames 工具

**Files:**
- Modify: `src/tools/animation_tools.py`
- Test: `tests/test_animation_preset_tools.py`

- [ ] **Step 1: 写失败测试 `tests/test_animation_preset_tools.py`**

```python
"""动画辅助增强工具测试。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.animation_tools import register_animation_tools


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool
    register_animation_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_apply_timing_preset_calls_batch_script(setup):
    """apply_timing_preset 应调用 set_frame_durations.lua（批量）。"""
    tools, sm, runner = setup
    # get_frame_info 返回 4 帧用于构造 durations
    runner.run_script.side_effect = [
        {"success": True, "stdout": '{"frames": 4, "durations": [0.1,0.1,0.1,0.1]}', "stderr": ""},
        {"success": True, "stdout": "OK", "stderr": ""},
    ]
    result = tools["apply_timing_preset"](session_id="s1", animation_type="walk")
    assert result["success"] is True
    # 第二次调用应是 set_frame_durations.lua
    last_call = runner.run_script.call_args_list[-1]
    assert last_call[0][0] == "set_frame_durations.lua"


def test_apply_timing_preset_rejects_unknown_type(setup):
    tools, _, _ = setup
    result = tools["apply_timing_preset"](session_id="s1", animation_type="fly")
    assert result["success"] is False


def test_draw_animation_frames_calls_script(setup):
    """draw_animation_frames 应调用 draw_animation_frames.lua。"""
    tools, _, runner = setup
    result = tools["draw_animation_frames"](
        session_id="s1",
        grids="RRR/RRR/RRR|GGG/GGG/GGG",
        colormap="R=#FF0000,G=#00FF00,.=transparent",
    )
    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "draw_animation_frames.lua"


def test_export_onion_skin_preview_returns_image(setup):
    """export_onion_skin_preview 应返回 Image 对象。"""
    tools, sm, runner = setup
    with patch("src.tools.animation_tools.Image") as mock_image:
        mock_inst = MagicMock()
        mock_image.return_value = mock_inst
        result = tools["export_onion_skin_preview"](session_id="s1", frame=2)
        assert result is mock_inst
```

注：`test_export_onion_skin_preview` 需要 `from unittest.mock import patch`，文件头 import 补上。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_animation_preset_tools.py -v`
Expected: FAIL

- [ ] **Step 3: 在 `src/tools/animation_tools.py` 顶部补充 import**

```python
from pathlib import Path
from fastmcp.utilities.types import Image
from src.resources import _TIMING_PRESETS
```

- [ ] **Step 4: 在 `register_animation_tools` 函数末尾新增三个工具**

```python
    # ===== 动画辅助增强工具（docs §7）=====

    _TIMING_TYPES = set(_TIMING_PRESETS.keys())

    @mcp.tool
    def apply_timing_preset(
        session_id: str, animation_type: str, frame_count: int = None
    ) -> dict:
        """★批量★ 按动画类型批量设置所有帧时长，替代 N 次 set_frame_duration。

        docs §7.2：不同动作用不同时长是专业动画关键。
        可用类型: idle(400ms), walk(125ms), run(80ms), attack_hit(160ms) 等。

        Args:
            session_id: 会话 ID
            animation_type: 动画类型（见 aseprite://timing/presets）
            frame_count: 实际帧数（可选，与建议范围不符时返回警告）
        """
        if animation_type not in _TIMING_TYPES:
            return {
                "success": False,
                "error": f"Unknown type: {animation_type}. Available: {sorted(_TIMING_TYPES)}",
            }
        preset = _TIMING_PRESETS[animation_type]
        duration_ms = preset["duration_ms"]

        # 先获取当前帧数
        info_result = runner.run_script("get_frame_info.lua", {
            "file": str(session_manager.get_ase_path(session_id)),
        })
        try:
            import json
            info = json.loads(info_result["stdout"].strip())
            frame_total = info.get("frames", 0)
        except (json.JSONDecodeError, KeyError):
            return {"success": False, "error": "Failed to get frame info"}

        if frame_total == 0:
            return {"success": False, "error": "No frames in canvas"}

        # 构造等长 durations 列表
        durations = ",".join([str(duration_ms)] * frame_total)

        # 帧数与建议范围不符则警告（不阻断）
        warning = ""
        if frame_count is not None:
            lo, hi = preset["frame_count_range"]
            if not (lo <= frame_count <= hi):
                warning = f"Warning: frame_count {frame_count} outside suggested range [{lo},{hi}]"

        result = _run_anim_script(session_id, "set_frame_durations.lua", {
            "durations": durations,
        })
        if warning:
            result["warning"] = warning
        return result

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def export_onion_skin_preview(session_id: str, frame: int = 1, scale: int = 4) -> Image:
        """导出洋葱皮叠加预览：当前帧(原色)+前一帧(红)+后一帧(蓝)。

        给 AI "洋葱皮眼睛"检查动画连贯性（docs §7.4/§11.3）。
        第 1 帧无前一帧、末帧无后一帧，仅叠加存在的帧。

        Args:
            session_id: 会话 ID
            frame: 中心帧号（1-indexed，默认 1）
            scale: 放大倍数（默认 4）
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        png_path = work_dir / f"onion_{frame}.png"

        result = runner.run_script("export_onion_skin.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "frame": str(frame),
            "scale": str(scale),
        })
        if not result["success"]:
            raise RuntimeError(
                f"Failed to export onion skin: {result.get('error', 'Unknown')}"
            )
        return Image(path=str(png_path))

    @mcp.tool
    def draw_animation_frames(
        session_id: str, grids: str, colormap: str,
        mode: str = "copy", layer: int = 1,
    ) -> dict:
        """★批量★ 一次绘制多帧动画，替代 N 次 add_frame+clear+draw_from_grid 循环。

        6 帧动画从约 20 次调用降到 1 次。
        grids 用 | 分隔每帧，帧内行用 / 分隔。
        例: grids="RRR/RRR|GGG/GGG" 表示 2 帧各 2 行。
        mode="copy" 新帧复制上一帧再绘 grid（推荐，适合局部变化）；
        mode="blank" 新帧空白再绘 grid。

        Args:
            session_id: 会话 ID
            grids: 多帧 grid，用 | 分隔帧，/ 分隔行
            colormap: 颜色映射，如 "R=#FF0000,.=transparent"
            mode: 建帧模式 copy/blank（默认 copy）
            layer: 目标图层（默认 1）
        """
        if not grids or not colormap:
            return {"success": False, "error": "grids and colormap are required"}
        if mode not in ("copy", "blank"):
            return {"success": False, "error": f"Invalid mode: {mode}. Use 'copy' or 'blank'"}
        return _run_anim_script(session_id, "draw_animation_frames.lua", {
            "grids": grids, "colormap": colormap, "mode": mode, "layer": str(layer),
        })
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_animation_preset_tools.py -v`
Expected: 4 passed

- [ ] **Step 6: 提交**

```bash
git add src/tools/animation_tools.py tests/test_animation_preset_tools.py
git commit -m "feat: 动画辅助增强工具（apply_timing_preset/export_onion_skin_preview/draw_animation_frames）"
```

---

## 阶段三：Tileset 工具集

### Task 7: Tileset 模板 Resources

**Files:**
- Modify: `src/resources.py`

- [ ] **Step 1: 在 `src/resources.py` 新增瓦片模板字典**

在 `_TIMING_PRESETS` 之后插入（基于 docs §8.2/§8.3，grass_dirt 示例含中心/边缘瓦片）：

```python
# 瓦片布局模板（docs §8.2/§8.3），grid/colormap 可直接传入 draw_from_grid
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
```

- [ ] **Step 2: 在 `register_resources` 内新增两个 tileset Resource**

```python
    @mcp.resource("aseprite://tileset/templates")
    def list_tileset_templates() -> str:
        """返回可用的瓦片布局模板列表（docs §8.2）。"""
        templates = {
            name: {"description": t["description"], "tile_size": t["tile_size"]}
            for name, t in _TILESET_TEMPLATES.items()
        }
        return json.dumps({"templates": templates})

    @mcp.resource("aseprite://tileset/templates/{name}")
    def get_tileset_template(name: str) -> str:
        """返回指定瓦片模板的完整 grid/colormap（可直接传入 draw_from_grid）。

        可用: grass_dirt_16x16, dungeon_16x16, water_grass_16x16
        """
        template = _TILESET_TEMPLATES.get(name)
        if not template:
            return json.dumps({"error": f"Template not found: {name}"})
        return json.dumps(template)
```

- [ ] **Step 3: 提交**

```bash
git add src/resources.py
git commit -m "feat: 新增 Tileset 模板 Resources（docs §8）"
```

---

### Task 8: create_tileset.lua + export_tiled.lua 脚本

**Files:**
- Create: `scripts/create_tileset.lua`
- Create: `scripts/export_tiled.lua`

- [ ] **Step 1: 创建 `scripts/create_tileset.lua`**

```lua
-- create_tileset.lua：创建瓦片画布并设置网格为瓦片尺寸
-- 参数: file, tile_size, cols, rows
-- 行为: 创建 tile_size*cols × tile_size*rows 画布，设网格=tile_size
local file = app.params["file"]
local tile_size = tonumber(app.params["tile_size"])
local cols = tonumber(app.params["cols"])
local rows = tonumber(app.params["rows"])

if not file or not tile_size or not cols or not rows then
    print("ERROR: file, tile_size, cols, rows are required")
    return
end

local width = tile_size * cols
local height = tile_size * rows

-- 创建新精灵（RGB 模式）
local sprite = Sprite(width, height, ColorMode.RGB)
if not sprite then
    print("ERROR: failed to create sprite")
    return
end

-- 尝试设置网格大小为瓦片尺寸（docs §8.5）
-- app.gridBounds 是可读写属性
local grid_set = false
if app.gridBounds then
    app.gridBounds = Rectangle(0, 0, tile_size, tile_size)
    grid_set = true
end

sprite:saveAs(file)
if grid_set then
    print("OK: created tileset " .. width .. "x" .. height .. " grid=" .. tile_size .. " at " .. file)
else
    -- 降级：网格未设置，提示瓦片尺寸
    print("OK: created tileset " .. width .. "x" .. height .. " (grid NOT set, tile_size=" .. tile_size .. ")")
end
```

- [ ] **Step 2: 创建 `scripts/export_tiled.lua`**（平铺拼接预览，检查接缝）

```lua
-- export_tiled.lua：把当前画布当单个瓦片，导出 repeat×repeat 拼接预览 PNG
-- 参数: file, output, repeat (重复次数，默认 2), scale (默认 1)
local file = app.params["file"]
local output = app.params["output"]
local rep = tonumber(app.params["repeat"] or "2")
local scale = tonumber(app.params["scale"] or "1")

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

local w = sprite.width
local h = sprite.height
local layer = sprite.layers[1]
local cel = layer:cel(1)
if not cel or not cel.image then
    print("ERROR: no image in frame 1")
    return
end
local src = cel.image

-- 创建拼接后的画布
local out_w = w * rep
local out_h = h * rep
local result = Image(out_w, out_h, sprite.colorMode)
result:clear()

-- 平铺复制
for ry = 0, rep - 1 do
    for rx = 0, rep - 1 do
        result:drawImage(src, rx * w, ry * h)
    end
end

-- 导出
local tmp_sprite = Sprite(out_w, out_h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(result)
if scale > 1 then
    tmp_sprite:resize(out_w * scale, out_h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print("OK: exported tiled preview " .. rep .. "x" .. rep .. " to " .. output)
```

- [ ] **Step 3: 提交**

```bash
git add scripts/create_tileset.lua scripts/export_tiled.lua
git commit -m "feat: 新增 create_tileset/export_tiled Lua 脚本"
```

---

### Task 9: tileset_tools.py 工具模块

**Files:**
- Create: `src/tools/tileset_tools.py`
- Test: `tests/test_tileset_tools.py`

- [ ] **Step 1: 写失败测试 `tests/test_tileset_tools.py`**

```python
"""Tileset 工具测试。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.tileset_tools import register_tileset_tools


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool
    register_tileset_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_create_tileset_canvas_calls_script(setup):
    tools, _, runner = setup
    result = tools["create_tileset_canvas"](
        session_id="s1", tile_size=16, cols=6, rows=3
    )
    assert result["success"] is True
    call_args = runner.run_script.call_args
    assert call_args[0][0] == "create_tileset.lua"
    params = call_args[0][1]
    assert params["tile_size"] == "16"
    assert params["cols"] == "6"


def test_create_tileset_canvas_rejects_bad_size(setup):
    tools, _, _ = setup
    result = tools["create_tileset_canvas"](
        session_id="s1", tile_size=20, cols=2, rows=2
    )
    assert result["success"] is False


def test_export_tiled_preview_returns_image(setup):
    tools, _, runner = setup
    with pytest.MonkeyPatch.context() as mp:
        # Image 需要文件存在，mock 它
        import src.tools.tileset_tools as mod
        mock_image = MagicMock()
        mp.setattr(mod, "Image", mock_image)
        result = tools["export_tiled_preview"](session_id="s1", repeat=2)
        assert mock_image.called
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_tileset_tools.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 创建 `src/tools/tileset_tools.py`**

```python
"""Tileset 工具：瓦片画布创建与拼接预览（docs §8）。

补齐当前完全缺失的 Tileset 制作能力，专注瓦片画布创建与接缝自检。
"""

from pathlib import Path

from fastmcp.utilities.types import Image

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_session_id


def register_tileset_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册 Tileset 工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    # 允许的瓦片尺寸（docs §8.1）
    _ALLOWED_TILE_SIZES = {16, 32, 64}

    def _run_tileset_script(session_id: str, script_name: str, params: dict) -> dict:
        """执行 Tileset 脚本的公共逻辑。"""
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        all_params = {"file": str(ase_path), **params}
        result = runner.run_script(script_name, all_params)
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Tileset operation failed"),
                "stderr": result.get("stderr", ""),
            }
        return {"success": True, "message": result.get("stdout", "").strip()}

    @mcp.tool
    def create_tileset_canvas(
        session_id: str, tile_size: int, cols: int, rows: int
    ) -> dict:
        """创建瓦片画布并设置网格为瓦片尺寸（docs §8.5）。

        画布尺寸 = tile_size × cols × tile_size × rows。
        网格=瓦片尺寸让 AI 清晰看到瓦片边界，避免越界污染相邻瓦片。

        Args:
            session_id: 会话 ID
            tile_size: 单块瓦片尺寸（仅支持 16/32/64）
            cols: 横向瓦片数
            rows: 纵向瓦片数
        """
        if tile_size not in _ALLOWED_TILE_SIZES:
            return {
                "success": False,
                "error": f"Invalid tile_size: {tile_size}. Must be one of {sorted(_ALLOWED_TILE_SIZES)}",
            }
        if cols < 1 or rows < 1:
            return {"success": False, "error": "cols and rows must be >= 1"}
        return _run_tileset_script(session_id, "create_tileset.lua", {
            "tile_size": str(tile_size), "cols": str(cols), "rows": str(rows),
        })

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def export_tiled_preview(session_id: str, repeat: int = 2, scale: int = 4) -> Image:
        """导出平铺拼接预览 PNG，检查瓦片接缝（docs §8.4/§11.5）。

        把当前画布当单个瓦片，导出 repeat×repeat 拼接图。
        Tileset 最大坑是接缝：单看正常，拼接才暴露。本工具是 AI 的"拼接预览眼"。

        Args:
            session_id: 会话 ID
            repeat: 每方向重复次数（默认 2，即 2x2）
            scale: 放大倍数（默认 4）
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        png_path = work_dir / f"tiled_{repeat}x{repeat}.png"

        result = runner.run_script("export_tiled.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "repeat": str(repeat),
            "scale": str(scale),
        })
        if not result["success"]:
            raise RuntimeError(
                f"Failed to export tiled preview: {result.get('error', 'Unknown')}"
            )
        return Image(path=str(png_path))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_tileset_tools.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/tools/tileset_tools.py tests/test_tileset_tools.py
git commit -m "feat: Tileset 工具模块（create_tileset_canvas/export_tiled_preview）"
```

---

## 阶段四：质量检查工具

### Task 10: standards Resources

**Files:**
- Modify: `src/resources.py`

- [ ] **Step 1: 在 `src/resources.py` 新增规范文档字典**

在 `_TILESET_TEMPLATES` 之后插入：

```python
# 规范检查规则文档（docs §2/§4/§5/§7，供 AI 按需读取）
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
```

- [ ] **Step 2: 在 `register_resources` 内新增 standards Resource**

```python
    @mcp.resource("aseprite://standards/{category}")
    def get_standards(category: str) -> str:
        """返回指定类别的规范检查规则（docs §2/§4/§5/§7）。

        可用: size, palette, timing, pixel_art
        """
        std = _STANDARDS.get(category)
        if not std:
            return json.dumps({"error": f"Standards category not found: {category}"})
        return json.dumps(std)
```

- [ ] **Step 3: 提交**

```bash
git add src/resources.py
git commit -m "feat: 新增 standards Resources（docs §2/§4/§5/§7）"
```

---

### Task 11: export_silhouette.lua + check_standards.lua

**Files:**
- Create: `scripts/export_silhouette.lua`
- Create: `scripts/check_standards.lua`

- [ ] **Step 1: 创建 `scripts/export_silhouette.lua`**

```lua
-- export_silhouette.lua：导出纯黑剪影 PNG（docs §3.6 剪影测试）
-- 参数: file, output (PNG 路径), scale
-- 行为: 所有非透明像素 -> 黑色，导出
local file = app.params["file"]
local output = app.params["output"]
local scale = tonumber(app.params["scale"] or "1")

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

local w = sprite.width
local h = sprite.height
local layer = sprite.layers[1]
local cel = layer:cel(1)
if not cel or not cel.image then
    print("ERROR: no image in frame 1")
    return
end
local src = cel.image

-- 创建剪影 Image
local silhouette = Image(w, h, sprite.colorMode)
silhouette:clear()
local black = app.pixelColor.rgba(0, 0, 0, 255)

for it in src:pixels() do
    local pc = it()
    if app.pixelColor.rgbaA(pc) > 0 then
        silhouette:drawPixel(it.x, it.y, black)
    end
end

-- 导出
local tmp_sprite = Sprite(w, h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(silhouette)
if scale > 1 then
    tmp_sprite:resize(w * scale, h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print("OK: exported silhouette to " .. output)
```

- [ ] **Step 2: 创建 `scripts/check_standards.lua`**（返回 JSON 规范报告）

```lua
-- check_standards.lua：遍历画布返回规范检查报告（JSON）
-- 参数: file
-- 检查: size(尺寸), color_count(颜色数), palette_consistency, timing(帧时长), pixel_art(半透明/孤立像素)
local file = app.params["file"]
if not file then
    print('{"error": "file is required"}')
    return
end

local sprite = app.open(file)
if not sprite then
    print('{"error": "cannot open file"}')
    return
end

local w = sprite.width
local h = sprite.height

-- 1. 尺寸检查
local size_pass = (w % 8 == 0 and h % 8 == 0)
local size_detail = w .. "x" .. h
local size_suggestion = "尺寸应为 8 的倍数（docs §2.1）"

-- 2. 颜色数与半透明/孤立像素检查
local color_set = {}
local color_count = 0
local semi_transparent = 0
local pixel_positions = {}

local layer = sprite.layers[1]
local cel = layer:cel(1)
local has_image = cel and cel.image
if has_image then
    local img = cel.image
    for it in img:pixels() do
        local pc = it()
        local a = app.pixelColor.rgbaA(pc)
        if a > 0 then
            if a < 255 then
                semi_transparent = semi_transparent + 1
            end
            local r = app.pixelColor.rgbaR(pc)
            local g = app.pixelColor.rgbaG(pc)
            local b = app.pixelColor.rgbaB(pc)
            local key = r * 65536 + g * 256 + b
            if not color_set[key] then
                color_set[key] = true
                color_count = color_count + 1
            end
            -- 记录像素位置用于孤立像素检测
            table.insert(pixel_positions, {x=it.x, y=it.y, c=key})
        end
    end
end

-- 孤立像素检测（被异色包围）
local pixel_map = {}
for _, p in ipairs(pixel_positions) do
    pixel_map[p.x .. "," .. p.y] = p.c
end
local isolated = 0
for _, p in ipairs(pixel_positions) do
    local neighbors = {
        pixel_map[(p.x-1) .. "," .. p.y],
        pixel_map[(p.x+1) .. "," .. p.y],
        pixel_map[p.x .. "," .. (p.y-1)],
        pixel_map[p.x .. "," .. (p.y+1)],
    }
    local same_count = 0
    local has_neighbor = 0
    for _, nc in ipairs(neighbors) do
        if nc then
            has_neighbor = has_neighbor + 1
            if nc == p.c then same_count = same_count + 1 end
        end
    end
    -- 四邻全异色视为孤立
    if has_neighbor == 4 and same_count == 0 then
        isolated = isolated + 1
    end
end

-- 3. 帧时长检查
local frame_total = #sprite.frames
local timing_pass = true
local timing_detail = "single frame"
if frame_total > 1 then
    local first_dur = sprite.frames[1].duration
    local all_same = true
    for i = 2, frame_total do
        if sprite.frames[i].duration ~= first_dur then
            all_same = false
            break
        end
    end
    timing_pass = not all_same
    timing_detail = all_same and "all frames same duration (violates docs §7.2)" or "varied durations"
end

-- 4. 构造 JSON 报告
local function check_item(pass, detail, suggestion)
    return string.format('{"pass": %s, "detail": "%s", "suggestion": "%s"}',
        pass and "true" or "false", detail, suggestion)
end

local report = string.format(
    '{"success": true, "checks": {"size": %s, "color_count": %s, "timing": %s, "pixel_art": {"semi_transparent": %s, "isolated_pixels": %s, "visual_review": "%s"}}, "stats": {"width": %d, "height": %d, "color_count": %d, "frames": %d}}',
    check_item(size_pass, size_detail, size_suggestion),
    check_item(color_count >= 4 and color_count <= 32, color_count .. " colors", "建议 4-32 色（docs §4.1）"),
    check_item(timing_pass, timing_detail, "不同动作用不同时长（docs §7.2）"),
    check_item(semi_transparent == 0, semi_transparent .. " semi-transparent pixels", "禁止半透明像素（docs §5.1）"),
    check_item(isolated == 0, isolated .. " isolated pixels", "可能为 jaggies/噪点（docs §5.2）"),
    "jaggies 形状/枕头阴影需 export_silhouette + get_canvas_preview 视觉复查（docs §5.2/§5.4）",
    w, h, color_count, frame_total
)

print(report)
```

- [ ] **Step 3: 提交**

```bash
git add scripts/export_silhouette.lua scripts/check_standards.lua
git commit -m "feat: 新增 export_silhouette/check_standards Lua 脚本"
```

---

### Task 12: quality_tools.py 工具模块

**Files:**
- Create: `src/tools/quality_tools.py`
- Test: `tests/test_quality_tools.py`

- [ ] **Step 1: 写失败测试 `tests/test_quality_tools.py`**

```python
"""质量检查工具测试。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.quality_tools import register_quality_tools


@pytest.fixture
def setup():
    session_manager = MagicMock()
    runner = MagicMock()
    session_manager.get_ase_path.return_value = Path("/tmp/canvas.ase")
    session_manager.get_work_dir.return_value = Path("/tmp/work")

    tools = {}
    mcp = MagicMock()

    def capture_tool(func=None, **kwargs):
        if func is None:
            return lambda f: capture_tool(f, **kwargs)
        tools[func.__name__] = func
        return func

    mcp.tool = capture_tool
    register_quality_tools(mcp, session_manager, runner)
    return tools, session_manager, runner


def test_check_canvas_standards_parses_json(setup):
    """check_canvas_standards 应解析 Lua 返回的 JSON 报告。"""
    tools, _, runner = setup
    runner.run_script.return_value = {
        "success": True,
        "stdout": '{"success": true, "checks": {"size": {"pass": true, "detail": "16x16", "suggestion": "x"}}, "stats": {"width": 16, "height": 16, "color_count": 5, "frames": 1}}',
        "stderr": "",
    }
    result = tools["check_canvas_standards"](session_id="s1")
    assert result["success"] is True
    assert result["stats"]["color_count"] == 5


def test_check_canvas_standards_handles_error(setup):
    tools, _, runner = setup
    runner.run_script.return_value = {
        "success": True, "stdout": '{"error": "cannot open file"}', "stderr": "",
    }
    result = tools["check_canvas_standards"](session_id="s1")
    assert result["success"] is False


def test_export_silhouette_returns_image(setup):
    tools, _, runner = setup
    with pytest.MonkeyPatch.context() as mp:
        import src.tools.quality_tools as mod
        mock_image = MagicMock()
        mp.setattr(mod, "Image", mock_image)
        result = tools["export_silhouette"](session_id="s1")
        assert mock_image.called
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_quality_tools.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 `src/tools/quality_tools.py`**

```python
"""质量检查工具：剪影测试与规范检查（docs §3.6/§5/§11）。

把 docs 的自检规范变成 AI 可调用的工具，交付前自动发现常见问题。
"""

import json
from pathlib import Path

from fastmcp.utilities.types import Image

from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.utils import validate_session_id


def register_quality_tools(mcp, session_manager: SessionManager, runner: AsepriteRunner):
    """注册质量检查工具到 MCP 服务器。

    Args:
        mcp: FastMCP 实例
        session_manager: 会话管理器
        runner: Aseprite 执行器
    """

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def export_silhouette(session_id: str, scale: int = 4) -> Image:
        """导出纯黑剪影 PNG（docs §3.6 剪影测试）。

        所有非透明像素变黑。剪影若不清晰则造型需调整。
        这是专业像素美术的招牌自检：纯黑也能辨识出是什么说明造型扎实。

        Args:
            session_id: 会话 ID
            scale: 放大倍数（默认 4）
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)
        work_dir = session_manager.get_work_dir(session_id)
        png_path = work_dir / "silhouette.png"

        result = runner.run_script("export_silhouette.lua", {
            "file": str(ase_path),
            "output": str(png_path),
            "scale": str(scale),
        })
        if not result["success"]:
            raise RuntimeError(
                f"Failed to export silhouette: {result.get('error', 'Unknown')}"
            )
        return Image(path=str(png_path))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def check_canvas_standards(session_id: str) -> dict:
        """检查画布是否符合 docs 规范，返回结构化报告。

        检查项（每项 pass/detail/suggestion）：
        - size: 尺寸是否为 8 的倍数（§2.1）
        - color_count: 颜色数是否在 4-32（§4.1）
        - timing: 多帧时是否统一帧率（§7.2，统一则警告）
        - pixel_art: 半透明像素/孤立像素（§5），jaggies 形状需视觉复查

        报告全 pass 可跳过 preview 直接导出（减少调用）。

        Args:
            session_id: 会话 ID
        """
        validate_session_id(session_id)
        ase_path = session_manager.get_ase_path(session_id)

        result = runner.run_script("check_standards.lua", {
            "file": str(ase_path),
        })
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Standards check failed"),
            }
        try:
            data = json.loads(result["stdout"].strip())
            if "error" in data:
                return {"success": False, "error": data["error"]}
            return data
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Failed to parse response: {result['stdout']}",
            }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_quality_tools.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/tools/quality_tools.py tests/test_quality_tools.py
git commit -m "feat: 质量检查工具（export_silhouette/check_canvas_standards）"
```

---

## 阶段五：集成与调用优化

### Task 13: server.py 注册新工具模块

**Files:**
- Modify: `server.py`

- [ ] **Step 1: 在 `server.py` 顶部补充 import**

在现有 `from src.tools.transform_tools import register_transform_tools` 之后加：

```python
from src.tools.tileset_tools import register_tileset_tools
from src.tools.quality_tools import register_quality_tools
```

- [ ] **Step 2: 在 `create_server` 内补充注册调用**

在 `register_transform_tools(mcp, session_manager, runner)` 之后加：

```python
    register_tileset_tools(mcp, session_manager, runner)
    register_quality_tools(mcp, session_manager, runner)
```

- [ ] **Step 3: 启动验证（手动）**

Run: `python -c "from server import create_server; create_server(); print('OK')"`
Expected: 输出 `OK`（无 import/注册错误）

- [ ] **Step 4: 提交**

```bash
git add server.py
git commit -m "feat: 在 server.py 注册 tileset_tools/quality_tools"
```

---

### Task 14: 现有工具描述补"勿循环"提示 + 批量工具描述强化

**Files:**
- Modify: `src/tools/draw_tools.py`
- Modify: `src/tools/animation_tools.py`

- [ ] **Step 1: 在 `src/tools/draw_tools.py` 的 `draw_pixel` 描述补提示**

找到 `draw_pixel` 工具的 docstring，在开头加：

```
⚠️ 勿循环调用绘制多像素，完整图案请用 draw_from_grid（1次=N像素），多帧动画请用 draw_animation_frames。
```

（同样为 `draw_line`/`draw_rect`/`draw_ellipse` 描述开头加此提示，因为它们已有"大量绘制用 draw_from_grid"的提示，此处在最前面统一加 `⚠️` 前缀强化。）

- [ ] **Step 2: 在 `src/tools/animation_tools.py` 的 `set_frame_duration` 与 `add_frame` 描述补提示**

`set_frame_duration` docstring 开头加：
```
⚠️ 勿逐帧循环调用，多帧请用 apply_timing_preset 批量设置。
```

`add_frame` docstring 开头加：
```
⚠️ 勿循环调用建多帧动画，多帧请用 draw_animation_frames 一次完成建帧+绘制。
```

- [ ] **Step 3: 提交**

```bash
git add src/tools/draw_tools.py src/tools/animation_tools.py
git commit -m "docs: 现有工具描述补勿循环提示（调用优化机制4）"
```

---

### Task 15: prompts.py 新增 create_tileset_prompt + 现有 prompt 补调用基准

**Files:**
- Modify: `src/prompts.py`

- [ ] **Step 1: 在 `src/prompts.py` 新增 `create_tileset_prompt`**

在 `register_prompts` 函数内、`multi_layer_prompt` 之后追加：

```python
    @mcp.prompt
    def create_tileset_prompt(
        description: str, tile_size: str = "16x16", cols: int = 6, rows: int = 3
    ) -> str:
        """生成瓦片集创作引导消息。

        Args:
            description: 瓦片集描述（如"草地与泥土过渡瓦片"）
            tile_size: 单块瓦片尺寸（如 16x16）
            cols: 横向瓦片数
            rows: 纵向瓦片数
        """
        return f"""请使用 Aseprite MCP 工具创建瓦片集：{description}

参数：{tile_size} 瓦片，{cols}x{rows} 布局

══════════════════════════════════════════
专业 Tileset 工作流程（docs §8）：
══════════════════════════════════════════

第1步：创建瓦片画布
  调用 create_tileset_canvas（tile_size={tile_size.split('x')[0]}, cols={cols}, rows={rows}）
  网格自动设为瓦片尺寸，清晰看到每块边界，避免越界污染相邻瓦片。

第2步：读取瓦片模板（可选参考）
  调用 aseprite://tileset/templates 查看可用模板
  调用 aseprite://tileset/templates/{{name}} 取具体 grid/colormap

第3步：绘制瓦片
  用 draw_from_grid 绘制单块瓦片（用 offset_x/offset_y 定位到瓦片格）
  完整一套需：中心块、边缘块、角块、过渡瓦片、装饰块（docs §8.3）

第4步：检查接缝（必须执行！）
  调用 export_tiled_preview（repeat=2）导出 2x2 拼接预览
  检查拼接处是否有可见接缝：
  - 边缘像素是否与相邻瓦片匹配？
  - 是否有 1 像素偏移？
  有接缝 → 修正边缘像素 → 再次 export_tiled_preview 验证

第5步：保存
  调用 save_sprite 保存

══════════════════════════════════════════
理想调用次数（docs §8 工作流）：
══════════════════════════════════════════
  create_tileset_canvas(1) → draw_from_grid(N块) → export_tiled_preview(1)
  → [修正] → export_tiled_preview(1) → save_sprite(1)
禁止：逐像素绘制瓦片、跳过接缝检查
"""
```

- [ ] **Step 2: 在 `create_animation_prompt` 末尾追加"调用基准"段**

在 `create_animation_prompt` 返回字符串的末尾、`动画规范:` 段之前插入：

```python
══════════════════════════════════════════
理想调用次数（{frame_count} 帧，调用优化基准）：
══════════════════════════════════════════
  create_sprite(1) → draw_animation_frames(1) → apply_timing_preset(1)
  → check_canvas_standards(1) → [pass]export_gif(1) = 5 次
禁止：逐帧循环 draw_from_grid / 逐帧 set_frame_duration / 每步必 preview

```

- [ ] **Step 3: 提交**

```bash
git add src/prompts.py
git commit -m "feat: 新增 create_tileset_prompt + 动画 prompt 补调用基准"
```

---

### Task 16: README 中英文同步更新工具表

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`

- [ ] **Step 1: 在 `README.md` 现有工具表后新增四个方向的工具表**

在"### 图像变换"表之后、"### 画布检查"之前插入新章节。具体：把 README 第 93 行 "共计 **38 个工具**" 改为 "共计 **48 个工具**"，并在图像变换表后追加：

```markdown
### 调色板增强

| 工具 | 说明 |
|------|------|
| `apply_preset_palette` | ★批量★ 应用内置预设调色板（db16/db32/aap64/nes/gameboy） |
| `derive_shading_palette` | 从主色派生三阶配色（色相偏移，默认自动应用） |
| `append_palette_colors` | ★批量★ 追加多个颜色到调色板 |

### 动画辅助

| 工具 | 说明 |
|------|------|
| `apply_timing_preset` | ★批量★ 按动画类型批量设置帧时长 |
| `draw_animation_frames` | ★批量★ 一次绘制多帧动画 |
| `export_onion_skin_preview` | 洋葱皮叠加预览（前后帧对比） |

### Tileset 工具集

| 工具 | 说明 |
|------|------|
| `create_tileset_canvas` | 创建瓦片画布并设网格 |
| `export_tiled_preview` | 平铺拼接预览（检查接缝） |

### 质量检查

| 工具 | 说明 |
|------|------|
| `export_silhouette` | 导出纯黑剪影（剪影测试） |
| `check_canvas_standards` | 画布规范自动检查（尺寸/颜色/帧时长/像素） |
```

- [ ] **Step 2: 在 `README_EN.md` 做对应英文翻译更新**

把工具总数 38 → 48，并追加对应英文表格（apply_preset_palette / derive_shading_palette / append_palette_colors / apply_timing_preset / draw_animation_frames / export_onion_skin_preview / create_tileset_canvas / export_tiled_preview / export_silhouette / check_canvas_standards）。

- [ ] **Step 3: 提交**

```bash
git add README.md README_EN.md
git commit -m "docs: README 中英文同步新增 10 个工具（38→48）"
```

---

### Task 17: 全量测试验证

- [ ] **Step 1: 运行全部单元测试**

Run: `python -m pytest tests/ -v --ignore=tests/test_e2e.py`
Expected: 所有非 e2e 测试通过

- [ ] **Step 2: 运行 e2e 测试（需真实 Aseprite）**

Run: `python -m pytest tests/test_e2e.py -v -m e2e`
Expected: e2e 测试通过（若无 Aseprite 环境则跳过，记录为已知）

- [ ] **Step 3: 启动 server 确认无错误**

Run: `python -c "from server import mcp; print('server OK, tools registered')"`
Expected: 输出 `server OK, tools registered`

---

## 自审清单

**Spec 覆盖：**
- §4 调色板增强 → Task 1/2/3 ✓
- §7 动画辅助 → Task 4/5/6 ✓
- §8 Tileset → Task 7/8/9 ✓
- §7.2 质量检查 → Task 10/11/12 ✓
- §3.2 资源命名空间 7 个 → Task 1/4/7/10 ✓
- §8 调用优化 4 机制 → 批量原语(Task 3/6) + 结构化检查(Task 12) + Prompt 基准(Task 15) + 描述强化(Task 14) ✓
- §10 文档更新 → Task 16 ✓
- §11 集成 → Task 13 ✓

**类型一致性：** 所有工具函数签名、Lua 参数名、Resource URI 在各 Task 间一致 ✓

**无占位符：** 所有代码完整，无 TBD/TODO ✓
