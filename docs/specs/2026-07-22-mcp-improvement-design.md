# Aseprite MCP 改进设计（Spec）

> 日期：2026-07-22
> 阶段：第一阶段 —— MCP 能力补齐
> 方案：B —— 规范即资源（docs 规范 → 结构化 Resources + 工具应用/检查）
> 后续第二阶段：Godot 扩展（独立 spec，本文件末尾附前瞻）

---

## 1. 概述

### 1.1 目标
基于 `docs/Aseprite游戏素材制作流程与规范.md` 全面改进 Aseprite MCP，补齐文档强调但 MCP 尚未提供的能力，让 AI 能按专业规范创作游戏素材。

### 1.2 范围
四个方向（用户已确认全选）：
1. 调色板增强（docs §4）
2. 动画辅助增强（docs §7）
3. Tileset 工具集（docs §8，当前完全缺失）
4. 质量检查工具（docs §3.6 / §5 / §11）

四个方向相对独立，纳入本单一 spec（共享架构），实现时按方向分批。

### 1.3 选定方案：方案 B
- **规范即资源**：docs 里的标准表结构化为 MCP Resources
- 新增工具侧重"应用预设 / 执行检查"
- 与项目 memory 教训一致：减少 AI 规划负担与 MCP 调用数
- 为 Godot 扩展预留"规范即资源"的统一模式

### 1.4 不在本阶段范围
- Godot 扩展（第二阶段独立 spec）
- 现有 38 工具的行为变更（仅扩展，不破坏兼容）

---

## 2. 背景与差距分析

对照 docs 逐节审视现有 38 工具，识别差距：

| docs 规范 | 现有能力 | 差距 |
|---|---|---|
| §4 预设调色板库（DB16/DB32/AAP-64/NES/GB）+ 阴影×0.7/高光×1.3 派生 | 仅固定 16 色资源 + `load_palette`(从文件) | 无内置预设库、无主色→三阶配色派生 |
| §7 帧时长规范表 + 洋葱皮 | `set_frame_duration` 单帧设置 | 无标准时长预设、无洋葱皮/前后帧预览 |
| §8 Tileset 制作（平铺模式/瓦片规划/过渡瓦片/无缝拼接） | 完全缺失 | 游戏素材核心能力缺口 |
| §3.6/§5 质量检查（剪影测试、jaggies/banding） | 仅 `get_canvas_preview` 视觉预览 | 无剪影测试、无规范自动检查 |
| §9 引擎对接（Godot .import/SpriteFrames） | `export_sprite_sheet` 仅出 PNG+JSON | 不生成引擎导入配置 → Godot 扩展切入点 |

---

## 3. 整体架构与资源命名空间

### 3.1 架构（不变）
沿用 FastMCP + subprocess + Lua 脚本模式，零侵入。新增内容：
- `src/tools/`：扩展 `palette_tools.py`、`animation_tools.py`、`inspect_tools.py`；新建 `tileset_tools.py`、`quality_tools.py`
- `scripts/`：新增 7 个 `.lua`
- `src/resources.py`：扩展 7 个新 Resource URI
- `server.py`：注册新工具模块

### 3.2 资源命名空间（在现有 `aseprite://` 下扩展）

| Resource URI | 返回 | 对应 docs |
|---|---|---|
| `aseprite://palette/presets` | `["db16","db32","aap64","nes","gameboy"]` | §4.3 |
| `aseprite://palette/presets/{name}` | `{name, description, colors:[...]}` | §4.3 |
| `aseprite://timing/presets` | 动画类型列表 | §7.2 |
| `aseprite://timing/presets/{type}` | `{type, description, frame_count_range, duration_ms}` | §7.2 |
| `aseprite://tileset/templates` | 模板列表 | §8.2 |
| `aseprite://tileset/templates/{name}` | `{name, description, tile_size, grid, colormap}` | §8.2 |
| `aseprite://standards/{category}` | 规则文档（`size`/`palette`/`timing`/`pixel_art`） | §2/§4/§5/§7 |

### 3.3 数据流
AI 读 Resource 取预设 → 调用工具应用预设到画布 → 工具走 Lua 执行 → 返回结果。
纯计算工具（如 `derive_shading_palette`）在 Python 层完成，不起 Lua 进程，降低开销。

### 3.4 Aseprite API 风险与备选
1. **网格设置**（`create_tileset`）：用 `app.command.Grid` 或 `app.gridBounds`；不可用则降级为"仅建画布 + 返回瓦片尺寸提示"，不阻断。
2. **平铺模式**（Tiled Mode 视图）：不依赖视图 API，改用 `export_tiled_preview` 导出 2×2 拼接 PNG 达到同等"检查接缝"目的。
3. **过渡瓦片自动生成**：不自动生成（算法复杂易错），改用模板资源 + `draw_from_grid`（带 offset 定位瓦片格）辅助绘制。

---

## 4. 调色板增强（docs §4）

### 4.1 新增 Resources
- `aseprite://palette/presets` → 预设名列表
- `aseprite://palette/presets/{name}` → `{name, description, colors:[...]}`
- 色值采用公开标准：DB16、DB32（DawnBringer 系列）、AAP-64、NES、Game Boy（4 色绿）。实现时填入准确色值，集中在 `resources.py` 的 `_PRESET_PALETTES` 字典。

### 4.2 新增工具

#### `apply_preset_palette(session_id, preset_name) -> dict`
- 读取预设 → 批量写入画布调色板
- Lua：`apply_palette.lua`，参数 `file` + `colors`（逗号分隔 `#RRGGBB`）
- 实现：先 `resize_palette` 到预设长度，再逐色 `setPaletteColor`
- 参数验证：`preset_name in {"db16","db32","aap64","nes","gameboy"}`，否则返回错误

#### `derive_shading_palette(base_color, shades=5, hue_shift=true, apply_to_palette=true, session_id?) -> dict`
- **纯 Python 计算，不起 Lua**
- 输入主色 `#RRGGBB`，按 docs 公式派生三阶配色
- 算法（`hue_shift` 控制色相偏移项，强度 `k=20`）：
  ```
  r,g,b = parse(base_color)
  highlight  = clamp(r*1.3 + k,     g*1.3 + k*0.3, b*1.3 - k)      # 亮部偏暖(黄)
  base       = (r, g, b)
  shadow     = clamp(r*0.7 - k*0.3, g*0.7,         b*0.7 + k)      # 暗部偏冷(蓝)
  deep_shadow= clamp(r*0.5,         g*0.5,         b*0.5 + k*0.5)
  outline    = #000000
  ```
  - `hue_shift=false` 时去掉所有 `k` 项（纯亮度缩放）
  - `clamp` 限制 0-255 并四舍五入
  - `shades=5` 默认返回 `[highlight, base, shadow, deep_shadow, outline]`
- 返回 `{palette: [...], colors_hex: [...]}`
- `apply_to_palette=true`（默认）时：`session_id` 必填，**调用 `append_palette_colors` 批量追加**到调色板末尾（1 次调用，不覆盖现有颜色，不逐色调 `set_palette_color`）
- `apply_to_palette=false` 时：仅返回配色，不修改画布（`session_id` 可空）

#### `append_palette_colors(session_id, colors) -> dict`
- ★批量★ 一次追加多个颜色到调色板末尾，替代 N 次 `set_palette_color` 循环
- Lua：`append_palette.lua`，参数 `file` + `colors`（逗号分隔 `#RRGGBB`），在现有调色板末尾逐色 `app.palette:addColor`，自动扩展调色板大小
- `derive_shading_palette(apply_to_palette=true)` 内部复用它（1 次完成 5 色追加）
- 职责区分：`apply_palette.lua` = **整板替换**（`apply_preset_palette` 用）；`append_palette.lua` = **尾部追加**（本工具与 `derive_shading_palette` 用）

### 4.3 原理
单纯降亮度使阴影发灰发脏；色相偏移（暗部偏冷模拟天空环境光、亮部偏暖模拟阳光）是专业做法。本工具把 docs §3.4/§4.4 经验固化成算法。

---

## 5. 动画辅助增强（docs §7）

### 5.1 新增 Resources
- `aseprite://timing/presets` → 动画类型列表
- `aseprite://timing/presets/{type}` → `{type, description, frame_count_range, duration_ms}`
- 预设内容来自 docs §7.2 表，集中在 `resources.py` 的 `_TIMING_PRESETS`：

  | type | frame_count_range | duration_ms |
  |---|---|---|
  | idle | 2-4 | 400 |
  | walk | 4-6 | 125 |
  | run | 6-8 | 80 |
  | attack_windup | 1-2 | 70 |
  | attack_hit | 1-2 | 160 |
  | attack_recover | 1-2 | 90 |
  | jump_start | 1-2 | 70 |
  | jump_apex | 1 | 150 |
  | jump_land | 1-2 | 100 |

### 5.2 新增工具

#### `apply_timing_preset(session_id, animation_type, frame_count?) -> dict`
- 按类型批量设置所有帧时长，一次调用替代 N 次 `set_frame_duration`
- Lua：`set_frame_durations.lua`，参数 `file` + `durations`（逗号分隔毫秒）
- 若提供 `frame_count` 且与 `frame_count_range` 不符 → 返回警告（不阻断）
- 参数验证：`animation_type` 白名单

#### `export_onion_skin_preview(session_id, frame, scale=4) -> dict`
- 导出叠加预览 PNG：当前帧（原色）+ 前一帧（红半透明）+ 后一帧（蓝半透明）
- Lua：`export_onion_skin.lua`，读取相邻三帧 cel image，逐像素合成带 alpha 叠加图，导出 PNG（返回 base64，与 `get_canvas_preview` 一致）
- 边界：第 1 帧无前一帧、末帧无后一帧，仅叠加存在的帧
- 给 AI "洋葱皮眼睛"检查连贯性（docs §7.4 / §11.3）

#### `draw_animation_frames(session_id, grids, colormap, mode="copy", layer=1) -> dict`
- ★批量★ 一次绘制多帧动画，替代 N 次 `add_frame + clear_region + draw_from_grid` 循环
- 参数：
  - `grids`：多帧 grid 列表，用 `|` 分隔每帧（帧内行仍用 `/` 分隔）。例 `"frame1row1/frame1row2|frame2row1/frame2row2"`
  - `colormap`：颜色映射（所有帧共用）
  - `mode`：`"copy"`=新帧复制上一帧再叠加 grid（适合只改局部的动画，推荐）；`"blank"`=新帧空白再绘 grid（适合全替换）
- Lua：`draw_animation_frames.lua`，循环：第 i 帧 → `sprite:newFrame()` → 若 copy 则复制上一帧 cel → 解析第 i 个 grid → 逐像素绘制
- **调用次数收益**：6 帧动画从 ~20 次（每帧 3-4 次）降到 **1 次**
- 属批量原语（只做"绘制多帧"一件事），不违背方案 B；含必要的 `newFrame` 是绘制前提，非不同操作打包

### 5.3 原理
docs §7.2：不要统一帧率，命中帧/顶点帧要更长——区分专业与业余的关键。`apply_timing_preset` 固化此规范。AI 无前后帧视觉记忆，`export_onion_skin_preview` 补齐。

---

## 6. Tileset 工具集（docs §8）

### 6.1 新增 Resources
- `aseprite://tileset/templates` → 模板列表
- `aseprite://tileset/templates/{name}` → `{name, description, tile_size, grid, colormap}`
- 首批模板（基于 docs §8.2/§8.3）：`grass_dirt_16x16`、`dungeon_16x16`、`water_grass_16x16`
- `grid`/`colormap` 可直接传入 `draw_from_grid`（offset 定位到瓦片格）

### 6.2 新增工具

#### `create_tileset_canvas(session_id, tile_size, cols, rows) -> dict`
- 创建 `tile_size*cols × tile_size*rows` 画布，设网格 = `tile_size`（docs §8.5）
- Lua：`create_tileset.lua`，建画布 + `app.command.Grid`/`app.gridBounds` 设网格
- 网格 API 不可用 → 降级仅建画布，返回 `tile_size` 提示
- `tile_size` 白名单 `{16,32,64}`

#### `export_tiled_preview(session_id, repeat=2, scale=4) -> dict`
- 把当前画布当单个瓦片，导出 `repeat×repeat` 拼接预览 PNG（docs §8.4 接缝检查）
- Lua：`export_tiled.lua`，`Image` 拼接，返回 base64 PNG
- 不依赖 Tiled Mode 视图 API，可靠

### 6.3 过渡瓦片路线
不新增自动生成工具。docs §8.3 的中心/边缘/角块/过渡瓦片由 `tileset/templates` 提供布局模板，AI 用 `draw_from_grid`（已有 `offset_x/offset_y`）绘制。更可控、不偏离现有风格。

### 6.4 原理
Tileset 最大坑是接缝：单看正常，拼接才暴露。`export_tiled_preview` 是 AI 的"拼接预览眼"；网格=瓦片尺寸防止越界污染相邻瓦片。

---

## 7. 质量检查工具（docs §3.6 / §5 / §11）

### 7.1 新增 Resources
- `aseprite://standards/{category}` → 规则文档，`category ∈ {size, palette, timing, pixel_art}`
- 内容来自 docs 对应章节，供 AI 按需读取

### 7.2 新增工具

#### `export_silhouette(session_id, scale=4) -> dict`
- 导出纯黑剪影 PNG（非透明像素 → 黑色）
- Lua：`export_silhouette.lua`，遍历像素，非透明设黑，导出 base64 PNG
- docs §3.6 剪影测试：剪影不清则造型需调整

#### `check_canvas_standards(session_id) -> dict`
- 遍历画布返回结构化规范报告
- Lua：`check_standards.lua`，返回 JSON
- 检查项，每项 `{pass: bool, detail: str, suggestion: str}`：

  | 类别 | 检查 | docs |
  |---|---|---|
  | size | width/height ∈ {8,16,32,64} 或 %8==0 | §2.1 |
  | color_count | 实际不同颜色数，建议 4-32 | §4.1 |
  | palette_consistency | indexed 模式下是否有像素色不在调色板内 | §11.4 |
  | timing | 帧数>1 时是否所有帧 duration 全相同（全同则警告） | §7.2 |
  | pixel_art.semi_transparent | 是否有 alpha<255 像素（错误抗锯齿） | §5.1 |
  | pixel_art.isolated_pixels | 被异色包围的单像素数（启发式 jaggies/噪点） | §5.2 |
  | pixel_art.visual_review | 提示：jaggies 形状/枕头阴影需 `export_silhouette`+`get_canvas_preview` 视觉复查 | §5.2/§5.4 |

### 7.3 像素检查务实边界
- **可机检项**直接判定：半透明像素、孤立单像素、颜色数
- **需视觉判断项**（jaggies 形状、枕头阴影 banding）：纯算法易误报，工具不强行判定，返回"建议视觉复查"提示，避免误导 AI

### 7.4 与现有工具关系
`get_canvas_preview`（视觉预览）保留；新工具是专项检查，互不替换。

---

## 8. 调用次数优化机制（治本）

> 硬约束：实际使用中 MCP 调用次数必须最小化，杜绝"几百次"调用，且不影响流程专业性。

### 8.1 问题来源诊断
"几百次调用"的真正大头是**循环调用同一原语**：

| 场景 | 旧调用数 | 根因 |
|---|---|---|
| 6 帧动画逐帧绘制 | ~20 | 每帧 add_frame+clear+draw+preview 循环 |
| 调色板逐色设置 | N | 逐色 set_palette_color 循环 |
| 逐帧设时长 | N | 逐帧 set_frame_duration 循环 |
| 盲目 preview 迭代 | 多轮 | 每步必 preview，无结构化判断 |

### 8.2 机制 1：批量原语（核心）
把"循环调用同一操作"改为"一次批量"。本 spec 新增 4 个批量工具：

| 批量工具 | 替代的循环 | 收益 |
|---|---|---|
| `draw_animation_frames` | N×(add_frame+clear+draw) | 6 帧 20 次 → **1 次** |
| `append_palette_colors` | N×set_palette_color | 5 色 5 次 → **1 次** |
| `apply_timing_preset` | N×set_frame_duration | 6 帧 6 次 → **1 次** |
| `apply_preset_palette` | N×set_palette_color | 整板 N 次 → **1 次** |

**批量原语 vs 复合工具的界限**（守住方案 B）：批量原语只做"同一操作的批处理"（绘制多帧 / 追加多色），不把建画布+调色板+绘制+描边等不同性质操作打包。`draw_animation_frames` 含 `newFrame` 是绘制前提，非不同操作打包。

### 8.3 机制 2：结构化检查替代盲目 preview
`check_canvas_standards` 返回结构化报告（每项 pass/detail/suggestion）。AI 据此判断：
- 报告全 pass → 跳过 preview，直接导出
- 有 fail → 针对性 preview + 修正
减少一半以上 preview 往返。preview 仍保留用于视觉判断（剪影/造型），不砍。

### 8.4 机制 3：Prompt 固化调用基准
每个新 prompt 写明**预期调用次数基准**与**禁止行为**。例（动画创作 prompt）：
```
理想流程（6帧）：
  create_sprite(1) → draw_animation_frames(1) → apply_timing_preset(1)
  → check_canvas_standards(1) → [pass]export_gif(1) = 5 次
禁止：逐帧循环 draw_from_grid / 逐色 set_palette_color / 每步必 preview
```
精灵创作 prompt 类似固化基准。给 AI 明确目标，而非靠它自行规划。

### 8.5 机制 4：工具描述强化（延续 memory 教训）
- 批量工具描述加 `★批量★` 前缀，注明"1 次 = N 帧/N 色"
- 单点工具（`draw_pixel`/`set_palette_color`/`set_frame_duration`/`add_frame`）描述加 `⚠️ 勿循环调用，N 个请用 XXX 批量版`
- 延续 memory 教训：AI 不会自动选高效工具 → 必须在描述里显式写明

### 8.6 预期效果
| 流程 | 优化前 | 优化后 |
|---|---|---|
| 6 帧行走动画 | ~30 次 | ~5 次 |
| 单精灵创作+迭代 | ~15 次 | ~6 次 |
| 5 色配色精灵 | ~12 次 | ~5 次 |

---

## 9. 错误处理
- 沿用现有模式：工具返回 `{success, error/...}`，Lua `print("ERROR: ...")`/`print("OK: ...")`
- 参数验证在 Python 层：`validate_color`、预设名/动画类型/瓦片尺寸白名单
- Aseprite API 不可用降级不阻断（§3.4）
- `session_id` 不存在 → 由 `SessionManager._get_session` 抛 `KeyError`，工具层捕获返回错误

---

## 10. 测试策略（沿用 `tests/` 模式）

### 10.1 单元测试（纯 Python，无需 Aseprite）
- `derive_shading_palette` 颜色计算（×0.7/×1.3 + 色相偏移，`hue_shift` 开关）
- 预设资源读取（`palette/presets`、`timing/presets`、`tileset/templates`、`standards`）
- 参数验证/白名单（`preset_name`、`animation_type`、`tile_size`）

### 10.2 e2e 测试（`@pytest.mark.e2e`，需真实 Aseprite）
每个新 Lua 脚本至少 1 个用例：
- `apply_palette.lua`、`append_palette.lua`、`set_frame_durations.lua`、`export_onion_skin.lua`
- `draw_animation_frames.lua`、`create_tileset.lua`、`export_tiled.lua`
- `export_silhouette.lua`、`check_standards.lua`

### 10.3 Resources 测试
验证 7 个新 URI 返回结构正确。

---

## 11. 文档更新
- `README.md` / `README_EN.md`：工具表新增 10 项（38 → 48），同步中英文
- `prompts.py`：新增 `create_tileset_prompt`；现有 prompt 补充"调用次数基准"与"禁止循环"条款（§8.4）
- 新工具描述引用 docs 对应章节作为规范依据
- 批量工具描述加 `★批量★`，单点工具加 `⚠️ 勿循环`（§8.5）

---

## 12. 规模汇总

| 类型 | 数量 | 明细 |
|---|---|---|
| 新工具 | 10 | apply_preset_palette、derive_shading_palette、append_palette_colors、apply_timing_preset、export_onion_skin_preview、draw_animation_frames、create_tileset_canvas、export_tiled_preview、export_silhouette、check_canvas_standards |
| 新 Lua 脚本 | 9 | apply_palette、append_palette、set_frame_durations、export_onion_skin、draw_animation_frames、create_tileset、export_tiled、export_silhouette、check_standards |
| 新 Resources | 7 | palette/presets×2、timing/presets×2、tileset/templates×2、standards×1 |
| 新测试文件 | 5 | test_palette_preset_tools、test_animation_preset_tools、test_tileset_tools、test_quality_tools、test_new_resources（按需合并） |

---

## 13. 实现阶段划分（供 writing-plans 参考）
1. **阶段一：调色板增强** —— `apply_preset_palette` + `derive_shading_palette` + `append_palette_colors` + 预设资源 + 2 Lua（apply_palette、append_palette）
2. **阶段二：动画辅助增强** —— `apply_timing_preset` + `export_onion_skin_preview` + `draw_animation_frames` + 时长资源 + 3 Lua（set_frame_durations、export_onion_skin、draw_animation_frames）
3. **阶段三：Tileset 工具集** —— `create_tileset_canvas` + `export_tiled_preview` + 模板资源 + 2 Lua
4. **阶段四：质量检查工具** —— `export_silhouette` + `check_canvas_standards` + standards 资源 + 2 Lua
5. **阶段五：集成与调用优化** —— `server.py` 注册、README 中英文同步、`create_tileset_prompt`、现有 prompt 补调用基准、批量/单点工具描述强化、测试补齐

每阶段独立可测、可提交。

---

## 14. Godot 扩展前瞻（第二阶段，独立 spec）
本阶段为 Godot 扩展预留的统一模式：
- **规范即资源**模式可复用：Godot 导入规范（.import 配置、SpriteFrames、像素完美项目设置）也做成 Resources
- **切入点**：`export_sprite_sheet` 后追加生成 Godot 资源文件
- **形态待定**（第二阶段 spec 决策）：同 server 新工具组 vs 独立 MCP server
- 不在本 spec 范围内，此处仅作架构预留说明
