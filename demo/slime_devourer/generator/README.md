# slime_devourer 生成器

32x32、4 方向 x 5 帧的"黏液吞噬怪"动作动画（待机 → 蓄力下压 → 张口突进 → 咬合 → 吞咽鼓包），
不是手画的：`monster.py` 用两块椭圆（颅骨 + 下颚绕嘴角铰点反向旋转）参数化产出字符网格，
`produce.py` 把它落到 Aseprite 并做质检。

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe   # 不设则依赖自动检测
python demo/slime_devourer/generator/produce.py             # 唯一入口：建会话 -> 一批 op -> inspect 质检 -> 逐像素校验 -> 打包
python demo/slime_devourer/generator/produce.py --preview   # 只出本地接触表 .build/sheet_preview.png，不启动 Aseprite
python demo/slime_devourer/generator/monster.py             # 打印 20 帧 ASCII，调形用
```

中间产物都在 `.build/`（已 gitignore）：`monster.ase`、`monster_sheet.png`、`monster_data.json`、
`frames/frame_1..20.png`、`sheet_preview.png`；会话状态在 `.build/work/`。
交付物在上级目录：四条方向 GIF、`slime_devourer_spritesheet.png`、`slime_devourer_devour.ase`。

## 职责边界

- **一个 `apply_operations` 原子批量画完整只怪**（27 个 op = 一次 Aseprite 进程）：
  `add_frames`(补到 20 帧) → 20 个 `paint_grid`（每帧一个）→ `set_durations`（逐帧五个不同时长）
  → 4 个 `add_tag`（`devour_down/left/right/up`）→ `save_sprite`。
  首帧由单独的 `create_sprite` 建出来拿 `session_id`，因为网格文件要写进会话目录。
- **网格文件写进 `<.build>/work/sessions/<session_id>/monster_NN.lua`**（在工作目录内，
  所以 `paint_grid` 免 `confirmed=true`）。内容是 Lua 表文件而非 JSON：本机构建的
  `json.decode` 返回 userdata，`pairs()`/`#` 都走不通，只能 `dofile`。
- **`inspect` 读回结构与指标**（`frame` 参数选帧；只读，永不改动文档）。
- **`run_lua` 只留导出**：精灵表 `app.command.ExportSpriteSheet` + 逐帧 PNG。逐帧 PNG 要先把
  每帧拷成一个临时单帧文档再 `saveCopyAs`——多帧文档上直接 `saveCopyAs("x.png")` 会写成
  `x1.png..xN.png`，拿不到确切文件名。

早期版本在这里写了两条不成立的前提，已删：

- ~~「op 注册表不能扩帧，`frame=2` 会报 frame index out of bounds，动画结构必须走逃逸舱」~~
  `add_frames` / `set_durations` / `add_tag` 三个结构 op 早就在注册表里；手写搭帧的 Lua 已删。
- ~~「inspect 对多帧文档会抛 FileNotFoundError，所以只能用 run_lua 探结构」~~
  `scripts/inspect.lua` 现在会先把临时副本压成单帧再导出 PNG，多帧文档可以正常 inspect。

像素侧同样不再走 `draw_rect`：旧版每方向一批、4 批共 3248 个 op（本机 310/310/306/327ms，
合计 1253ms，外加一次建结构的 `run_lua`），现在 27 个 op 一个原子批量，本机 340~420ms
（会话冷启动的那一次是 632ms）。

## 造型模型

侧视的嘴是"咬穿轮廓的缺口"而不是体内的一个洞：上颚抬起、下颚落下，中间楔形即口腔。
几何只产出语义 mask，明暗与描边在渲染阶段统一计算，所以 `right` 是 `left` 的 mask 水平镜像，
而光照仍固定左上——把 `left` 整帧镜像过去会差 42~68 个明暗像素，那正是光照没跟着翻的结果，
不是缺陷。改造型只需要动 `SIDE_CFG` / `FRONT_CFG` 与 mask 构造函数，重跑 `produce.py`。

## 质检（`produce.py` 的 `qa()`，读的是 inspect 回读的 metrics）

全绿才允许打包，任何一条不满足就 `SystemExit(1)` 并列出缺陷：

- `isolated_pixels` 20 帧全为 0（黏液怪身上孤立像素 = 脏点）。当前造型本来就没有孤点，
  这条是回归闸门：以后调形把描边画断，这里直接失败。
- `near_duplicate_colors` 由 6 帧报 `#F4F7E4`(牙) vs `#F6FFE8`(眼神光)（三通道差 2/7/4，全在
  阈值 8 内）收敛到 0：牙改成 `#E7EEDA`，与眼神光差 R15/G16，仍留在同一支冷色里，
  高亮层级（眼神光最亮）不变。
- `semi_transparent_pixels` 0（`paint_grid` 一律 alpha=255，GIF 的 1-bit 透明不会被半像素糊住）。
- **bbox 不许贴画布边**：`left`/`right` 的突进帧（8/13）颅顶描边原来压在画布第 0 行，等于被
  画布切掉；把 `SIDE_CFG[2].lean` 从 `(-3,-1)` 改成 `(-3,0)`（整帧下移 1px，形状不动），
  现在四周一律留有 1px 余量。
- **体积曲线**（bbox 尺寸 / coverage）：蓄力压扁、突进拉长最满、咬合收缩、吞咽把轮廓顶高，
  `produce.py` 会打表：

  | 相位 | down(正) | left | right | up(背) |
  |---|---|---|---|---|
  | idle | 22x26/0.479 | 23x27/0.504 | 23x27/0.504 | 22x26/0.479 |
  | windup | 24x24/0.479 | 24x26/0.522 | 24x26/0.522 | 24x24/0.496 |
  | lunge | 22x27/0.496 | 23x30/0.557 | 23x30/0.557 | 22x27/0.512 |
  | chomp | 24x25/0.488 | 23x26/0.510 | 23x26/0.510 | 24x25/0.506 |
  | swallow | 22x28/0.496 | 22x28/0.522 | 22x28/0.522 | 22x28/0.496 |

  背视原来越张口越宽（`wide = 1 + 0.055 * mx` 不设上限，突进时颅骨半径 8.8→12.0，剪影 26 宽
  对正视图的 22 宽，同一瞬间胖了一号），现在给它封顶到"最多比正视颅骨宽 1px 半径"，
  正/背剪影在每个相位完全一致，方向切换不再突然换体型。
- **方向自洽**：`right` 的 alpha mask 必须等于 `left` 的水平镜像，bbox 尺寸相同、
  x 满足 `x_left + x_right + width == 32`。
- **帧时长逐帧不同**：五个相位 `[0.2, 0.1, 0.08, 0.09, 0.22]` 秒（本机 `Frame.duration` 按秒
  解释）两两不同，`set_durations` 一次写满 20 帧，inspect 回读逐帧比对（±5ms）。
  打包时再断言 GIF 里确实是 `[200, 100, 80, 90, 220]` 且 5 帧没被编码器合并
  （五帧两两不同，`n_frames == 5` 是这条约定的探针）。

校验之外还有一条硬闸门：`verify()` 把每帧导出的 PNG 与 `monster.py` 的设计矩阵逐像素比对，
20 帧必须全 0 差；不为 0 就打印差异像素并不打包。
