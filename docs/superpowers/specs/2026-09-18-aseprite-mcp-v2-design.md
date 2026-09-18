# Aseprite MCP v2 设计与改造规范

- 日期：2026-09-18
- 状态：已批准（brainstorming 架构路径产物）
- 目标读者：实现者（人或 agent）
- 关联：`AGENTS.md`（仓库约定）、`README.md`、`CLAUDE.md`（部分过期）

## 1. 背景与目标

现有 Aseprite MCP 有 75 个工具、69 个 Lua 脚本、247 个测试，但存在会破坏用户数据的缺陷、每次调用一进程的性能模型、三套混用的返回格式，以及大量与竞品同质却更弱的低层工具。

本次改造的第一性原理：**LLM 的瓶颈不是工具数量，而是（a）空间能力弱、（b）往返成本高、（c）状态不可信。** 因此 v2 的目标是：

1. 把工具面从 75 收敛到 **3 个**，把能力搬进 **op 注册表**；
2. 让所有变更走 **单进程、单事务、可校验、可回滚** 的 `apply_operations`；
3. 让 `inspect` 成为唯一且安全的感知回路（图像 + 量化指标，一次调用）；
4. 把"怎么画好"沉淀为 **Skill 配方** 与**确定性美术算子**，而不是更多原语；
5. 升级到 FastMCP 4 / MCP `2026-07-28`，拿到结构化输出、确认式破坏性操作、后台任务与 Skills。

**成功标准**：阶段 0-2 完成后，默认 CLI 模式下"画 → 看 → 改 → 撤销"闭环真实可信且每次批量调用只启一次 Aseprite 进程；阶段 3-5 完成后，一个不懂像素画的用户能让 agent 产出游戏可用的 sprite 与 atlas。

## 2. 非目标

- 不重写 Aseprite Lua 侧全部逻辑；现有脚本作为 op 实现逐步收敛。
- 不实现多级 CLI undo 历史（Live 模式用 Aseprite 原生多级）。
- 不做用户自定义 op 注册（扩展用 `run_lua`）。
- 不引入 sampling / roots / logging（MCP 2026 已弃用）。
- 不做 HTTP/远程传输；保持 stdio MCP + 本地 WebSocket。

## 3. 现状缺陷清单（必须修复）

### P0 正确性

| # | 缺陷 | 位置 | 修复方式 |
|---|---|---|---|
| P0-1 | `get_canvas_preview(scale>1)` 在 Live 模式永久 resize 用户文档，且被标 `readOnlyHint` | `scripts/export_png.lua:37-41`、`src/tools/inspect_tools.py:25` | `inspect` 永远在临时副本上缩放；修正注解 |
| P0-2 | CLI undo 只要脚本退出码 0 就报成功，文件恢复分支不可达 | `src/tools/batch_tools.py:153-155` | v2 统一的单级备份交换（见 §6.3） |
| P0-3 | CLI redo 空操作却报成功 | `src/tools/batch_tools.py:175-177` | 同上；无法 redo 时返回 `no_more_redo` |
| P0-4 | 只有 3 个工具写 `undo_backup.ase`，其余变更无法 undo | `layer_tools.py:142,154`、`batch_tools.py:57` | 所有 mutating 批量在 Python 侧统一备份 |
| P0-5 | 选区跨调用不可用：`_mcp_load_selection` 从未调用，`delete_selection` 不读 mask；CLI 每调用一进程导致选区丢失 | `mcp_common.lua:323`、`selection_tools.py:97-99` | 事务内核使同批 op 共享进程内真实 `sprite.selection`；移除 mask 文件方案 |
| P0-6 | `get_canvas_info` 尺寸缓存漂移（仅 import_png 更新） | `session.py:94-101`、`sprite_tools.py:236` | 元数据一律从文件/Lua 推导，删除 Python 缓存 |
| P0-7 | Live `create_sprite` 可能复用活动 sprite，但 Python 总建新 session_id | `mcp_common.lua:85-93`、`sprite_tools.py:36-49` | `create_sprite` 语义明确为"新建文档"，Live 下新建 `Sprite()` 而非复用 |
| P0-8 | WS 启动失败回退 CLI 但 `config.mode` 仍为 `"ws"` | `server.py:57-63` | 回退时同步 `config.mode="cli"` 并在信封 `warnings` 中说明 |

### P1 接口与工程卫生

- 返回约定三套混用（标准包 / 抛异常 / 裸 dict）→ 统一信封（§5）。
- 查询工具内联 `json.loads` 而不复用 `parse_json_output` → 随工具重构消除。
- 8 个重复的 `_run_*_script` 薄封装、死代码 `run_script_path`、`_mcp_pixel/line/rect/ellipse/fill/clear_rect`、`ensure_pillow_available` → 清理或复活。
- `.gitignore` 误伤 `tests/` 与 `docs/` **已修复**（本次提交）。
- 测试几乎全为 mock 调用断言，抓不到 Live/CLI 行为差异 → §11 测试策略。

### P2 能力缺口（竞品已具备）

slices、tilemap 编辑、文字、ordered/Bayer dither、对称与自定义笔刷、linked cel、参考图分析与调色板量化、AA 建议、按层/按 tag 导出、scaffold 工作流、`health_check`、自动探测 Aseprite、零安装分发。纳入 §8、§10。

## 4. 关键决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 路线 | 极简内核 + op 注册表 | 用户选定；工具面最小化，能力不缩水 |
| API 兼容 | 允许破坏性重构，不保留旧工具名 | 用户选定；换取干净的接口与结构化输出 |
| 持久进程 | **放弃** `aseprite --shell` | Spike 证实其为交互式 REPL：管道无输出、不消费 `app.exit()`、EOF 不退出 |
| 持久状态 | 单次 `aseprite -b` 内多 op + 现有 WS 扩展 | `--shell` 不可脚本化；WS 已存在 |
| Undo 深度 | CLI 单级，Live 原生多级 | YAGNI；诚实返回失败优于假成功 |
| op 库组织 | 分类 `ops_*.lua`，编译期按需 `dofile` | 单文件巨石难维护；`dofile` 成本可忽略 |
| 临时脚本 | session 工作目录固定 `_batch.lua` + 每会话锁 | 串行化同会话的读改写，消除竞争 |
| 导出实现 | 原生 CLI 标志（`--sheet/--data/--trim/...`） | 引擎级 atlas，取代自写 Lua 导出 |
| 基础设施 | FastMCP 4（`>=4.0.2,<5`） | 已 GA；解锁结构化输出、guard-pattern 确认、Tasks、Skills |

## 5. 工具面（3 个）

| 工具 | 职责 |
|---|---|
| `apply_operations(session_id?, ops[], {atomic=true, dry_run=false, confirmed=false})` | 唯一变更入口。op 列表编译为单个 Lua 程序，在单进程单事务中执行 |
| `inspect(session_id, {view, layers?, frames?, scale?, metrics?})` | 唯一感知入口。返回图片 + 结构化指标；只读、永不改动文档 |
| `run_lua(session_id, code, unsafe=false)` | 逃逸舱。未覆盖能力兜底；`unsafe=true` + 确认后执行 |

- **会话生命周期是 op**：`create_sprite` / `open_sprite` / `save_sprite` / `close_session` 在 `ops[]` 中。`apply_operations(session_id=None)` 且首 op 为 create/open 时，Python 先创建 session 再执行。
- **会话列表是资源**：沿用 `aseprite://sessions`，不占工具位。
- 旧工具名不保留。

## 6. 执行内核

### 6.1 OpSpec 注册表

```
OpSpec = {
  name: str,                      # 稳定标识，如 "draw_rect"
  category: str,                  # draw|layer|frame|palette|selection|transform|export|session|meta
  params: type[BaseModel],        # 生成 JSON Schema；校验与目录共用
  result: type[BaseModel],        # op 级 data 形状
  backend: "lua" | "cli",         # 默认 lua；导出类为 cli
  lua: str | None,                # 如 "_mcp_op_draw_rect"
  cli_flags: callable | None,     # backend=cli 时由参数生成 aseprite 标志
  mutating: bool,
  destructive: bool,
}
```

- 注册表是唯一事实来源；op 目录由它序列化为资源/Skill。
- 校验顺序：Pydantic 校验 → `dry_run` 返回将执行的 op 计划 → 编译 → 执行。
- 未知 op 名、参数类型错误一律 `invalid_args`，不启动 Aseprite。

### 6.2 编译契约

`apply_operations` 把 `ops[]` 编译为一段临时 Lua 程序（`<work_dir>/_batch.lua`）：

```
-- 1. if not _G._mcp_common_loaded then dofile(mcp_common.lua) end
-- 2. dofile(仅本次用到的 ops_<category>.lua)
-- 3. local sprite = _mcp_get_sprite(file)
-- 4. local results = {}
-- 5. atomic=true:  app.transaction("MCP: N ops", function() ... end)
--    atomic=false: 逐 op pcall，记录 ok/err
-- 6. print("\n__MCP_JSON__" .. json.encode(results))
-- 7. backend=cli 的导出 op 在事务外由 Python 单独 spawn 原生 CLI
```

- **参数以 Lua 字面量嵌入生成程序**，不再走 `--script-param`（绕开 Aseprite 无 `loadstring`、`app.params` 仅字符串的限制）。
- 复用现有 `runner.run_script_path()`（CLI 与 WS 均已实现）。
- **WS 桥协议不变**：仍传脚本绝对路径，params 置空。
- 事务内任一 op 失败：记录 `op_index`，事务整体回滚，信封 `ok=false`。

### 6.3 Undo / Redo

| 模式 | 变更前 | undo | redo |
|---|---|---|---|
| CLI | 复制 `canvas.ase` → `undo_backup.ase`（每次 mutating 批量，Python 统一执行） | 当前文件 → `redo_backup.ase`；`undo_backup.ase` → `canvas.ase` | `redo_backup.ase` → `canvas.ase` |
| Live | 无 | `app.command.Undo()` | `app.command.Redo()` |

- CLI 语义为**单级**，对应"上一次 `apply_operations`"。
- 无备份时返回 `ok=false, code="no_more_undo"|"no_more_redo"`，绝不假成功。

### 6.4 并发与文件

- 每会话一把锁（Python 侧），串行化 `apply_operations`；固定 `_batch.lua` 覆盖写。
- `inspect` 同样持锁，避免读到写入中途的 `.ase`。
- 生成脚本随 session 工作目录清理。

## 7. 结果契约

所有工具返回同一信封（Pydantic 模型 → FastMCP 4 `outputSchema` + `structuredContent`）：

```
{
  "ok": bool,
  "session_id": str | null,
  "mode": "cli" | "ws",
  "op_results": [{"op": str, "ok": bool, "data": object}],
  "artifacts": [{"kind": "png|gif|json|ase", "path": str, "role": str}],
  "warnings": [str],
  "changed": bool,
  "undo": {"mode": "transaction|file_backup", "available": bool},
  "timing_ms": int,
  "error": {"code": str, "message": str, "hint": str, "op_index": int | null} | null
}
```

- 错误分类（稳定枚举）：`invalid_args`、`session_not_found`、`aseprite_not_found`、`unsupported_in_mode`、`op_failed`、`script_error`、`lua_runtime_error`、`file_error`、`no_more_undo`、`no_more_redo`、`confirmation_required`。
- 运行期失败不抛异常；仅 Python 内部编程错误允许抛出。
- `atomic=false` 时允许部分成功，逐 op 标注。
- `dry_run=true` 只编译与校验，不启进程、不写文件，`changed=false`。

## 8. 感知回路（`inspect`）

- **双载荷**：图片内容 + `metrics`（v4 `structuredContent`）。
- **视图**：`composite`（默认）｜`layers[]`/`frames[]`｜`onion`｜`silhouette`。
- **安全**：永远导出临时副本；只允许整数最近邻缩放；绝不 `resize`/保存活动文档。
- **指标**（Lua 出结构 + Python/PIL 出图像统计）：尺寸、调色板、颜色数、近重复色、半透明像素数、非透明包围盒、覆盖率、网格偏移（mixels）、孤立噪点、帧间 diff（变化像素/百分比/包围盒）、跨帧调色板漂移。
- 产物 `preview.png` 登记为 artifact，可经 resource 复用。

## 9. 美术算子与工作流

### 9.1 新增 op

- 绘制增强：dither（Bayer/有序 + 误差扩散）、多停靠渐变+抖动、outline（内/外、4/8 连通）、AA 建议与应用、symmetrize/mirror。
- 调色板：参考图取色、量化（中位切分/k-means）、色相偏移 shading ramp、近重复色合并。
- 结构：slices、linked cel、tilemap 编辑、按层/按 tag 导出、tileset 导出。
- 质量门：`check_standards`、silhouette、颜色数、网格检查可组合。

### 9.2 原生 CLI 导出（backend=cli）

`export_atlas` 等映射到 `aseprite -b file.ase --sheet … --data … --format json-hash|json-array --sheet-type horizontal|vertical|rows|columns|packed --trim --shape-padding … --split-layers|--split-tags --frame-range … --list-tags`，产出引擎可用的 PNG + JSON。

### 9.3 Skill 配方（FastMCP 4 `SkillsDirectoryProvider`）

`skills/` 目录承载：op 目录与速查、角色脚手架、idle/walk 动画、tileset、图标集、9-slice、交付前自检清单。每份配方 = op 序列 + 验证步骤。

## 10. 安全与协议

- 注解齐备且正确：`readOnlyHint`（`inspect`）、`destructiveHint`（`run_lua`、`close_session`、`clear_*`）、`idempotentHint`、`openWorldHint=false`。
- 破坏性确认：`apply_operations` 检测到 destructive op 或 `run_lua` 时，现代客户端用 v4 guard pattern（`InputRequiredResult`），旧客户端回退 `ctx.elicit(response_type=bool)`；缺确认返回 `confirmation_required`。
- `run_lua` 必须 `unsafe=true` 且确认。
- 日志走 stderr；不使用已弃用的 sampling/roots/logging。

## 11. 测试策略

1. **注册表与校验**：每个 OpSpec 的 schema、默认值、未知 op、类型错误。
2. **编译 golden**：ops[] → 生成 Lua 文本快照，保证结构稳定可审。
3. **执行桩**：假 `aseprite` 可执行文件记录 argv/stdin，验证单进程、事务包裹、参数嵌入。
4. **备份/undo/redo**：CLI 单级语义、`no_more_*`、Live 分支（mock）。
5. **inspect 安全**：断言临时副本缩放、活动文档不变（回归 P0-1）。
6. **契约**：统一信封、错误枚举、`dry_run`、部分成功。
7. **e2e**（`-m e2e`，无 Aseprite 自动跳过）：create → batch draw → inspect → undo → export_atlas。
8. 迁移期间现有 247 个测试保持通过，随工具废弃逐步替换。

## 12. 分发与运维

- 自动探测 Aseprite：`ASEPRITE_PATH` 覆盖 + PATH / Steam / Program Files / LOCALAPPDATA；删除硬编码 dev 路径。
- `uvx` / `pipx` / Docker；console entrypoint。
- `health_check`：Aseprite 版本、路径、脚本目录、WS 连通性、Python 依赖。
- 文档：README/README_CN 工具目录更新为 3 工具 + op 目录；Live 模式说明保留。

## 13. 阶段划分与验收

| 阶段 | 内容 | 验收 |
|---|---|---|
| 0 | FastMCP 4 升级、`.gitignore`、Aseprite 路径探测、依赖锁定 | 247 测试通过；`server.py` 在 v4 正常列出工具 |
| 1 | Op 注册表 + 编译 + 统一信封 + undo/redo + 3 工具骨架 | `draw_rect`/`fill_region` 经 `apply_operations` 单进程执行；dry_run；单级 undo/redo 真实生效 |
| 2 | `inspect` 安全感知回路 | P0-1 回归测试通过；一次调用返回图像+指标 |
| 3 | 美术 op + Skill 配方 | dither/ramp/outline/palette 量化可用；Skill 可被客户端发现 |
| 4 | 原生 CLI 导出 | `export_atlas` 产出 PNG+JSON，含 trim/pack/split |
| 5 | 分发、`health_check`、文档 | `uvx` 可跑；README 更新；自动探测生效 |

每个阶段独立发布，测试全绿；阶段 0-2 是"可信最小闭环"，优先完成。

## 14. 风险与回退

| 风险 | 缓解 |
|---|---|
| FastMCP 4 新依赖链（MCP SDK v2 / httpx2）不稳 | 锁精确版本；阶段 0 先跑通全部测试再动架构 |
| 生成 Lua 嵌入字面量的注入/转义问题 | 仅用 Python 序列化的受限字面量（字符串转义、数字、布尔、受限表），单测覆盖 |
| WS 模式与 CLI 行为差异 | op 层保持 mode 无关；差异只在保存/undo；e2e 双模式各跑一次 |
| 破坏性重构伤现有用户 | 用户已确认；README 提供迁移说明 |
| 阶段 1 一次性改动过大 | 按 op 类别分批迁移，旧脚本保留到对应 op 验证通过后再删 |

## 15. 交付物

- 本 spec（`docs/superpowers/specs/2026-09-18-aseprite-mcp-v2-design.md`）
- 实现计划（writing-plans 产物）
- v2 代码、Skill 目录、测试、更新后的 README/AGENTS.md
