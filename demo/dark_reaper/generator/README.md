# dark_reaper 生成器

32x32 暗黑死神，4 方向 x 6 帧行走循环。

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py          # 建会话 -> 一个原子批量画完 24 帧 -> 逐帧质检 -> 逐像素校验 -> 打包
python reaper.py           # 不碰 Aseprite，只看 ASCII
python reaper.py --sheet   # 本地接触表 .build/reaper_sheet.png
```

产物写到上级 `demo/dark_reaper/`：`dark_reaper_walk_{down,left,right,up}.gif`（4x，每个 6 帧）、
`dark_reaper_spritesheet.png`（192x128）、`dark_reaper_walk.ase`（24 帧 + 4 个
`walk_*` tag）。中间产物在 `.build/`（已 gitignore）。

## 画这 24 帧只用 v2 工具面

| | 旧（op 注册表还不能扩帧时） | 现在 |
| --- | --- | --- |
| 建结构 | `run_lua` 手写 Lua：`newFrame` / 建空 cel / 设 duration / `newTag` | `add_frames` + `set_durations` + 4x `add_tag` |
| 像素 | 4616 个 `draw_rect`，分 4 批，`timing_ms` 合计 1332ms | 24 个 `paint_grid`（一帧一个），与结构同一个批量 |
| 一次画完要几个 op / 几次 Aseprite 进程 | 4618 op / 7 次（建会话、建结构、4 批像素、保存） | **31 op / 1 次**，`timing_ms` 实测 371-673ms、零警告 |

那 31 个 op 是一个原子批量：`add_frames{count: 23}` → 24x `paint_grid` →
`set_durations{[0.12] * 24}` → 4x `add_tag` → `save_sprite`。
`add_frames` 必须排在 `paint_grid` 前面：新文档只有 1 帧，op 会自动补 cel，但**不会**自动补帧。

- 每帧一个 Lua 网格文件（`reaper.py` 的 `grid_lua()`，行是字符串、`.` 是透明），
  写进**会话工作目录** `<.build>/work/sessions/<session_id>/reaper_NN.lua`，
  所以 `paint_grid` 免 `confirmed=true` —— 见 `AGENTS.md` 的门闩约定：文件在工作目录内即视为可信输入。
- `run_lua` 只剩导出（`ExportSpriteSheet` + `saveCopyAs`）：工具面没有 export op，
  这是逃逸舱的正当用途。多帧文档上 `saveCopyAs("frame.png")` 会写成 `frame1.png…frame24.png`
  （永远不会写 `frame.png`），逐帧校验吃的就是这 24 个文件。

## 质检是指标，不是"没报错"

`produce.py` 先对 24 帧逐帧 `inspect`（24 次无头进程，实测约 6s，是脚本里最贵的一段；
全程约 20-23s，比旧版的 16.5s 慢，慢就慢在质检从"只看第 1 帧"变成"每帧都看"），
任一条不达标就失败、不打包；然后才把导出帧与 Python 侧设计网格逐像素比对（24/24 帧 0 像素差）。
每帧还顺带核对文档级事实：`frames_total == 24`、tag 列表 == `walk_down/left/right/up`
（`inspect` 只读，但万一哪天它改动原文档，这里就会响）。GIF 侧另有断言：每方向 6 帧两两不同，
否则编码器会静默合并相同帧。

这套指标在本机跑出来的两处硬伤，已经改回 `reaper.py` 的模型：

- **`bbox` 底边**：迁移后第一次逐帧 inspect，16 帧是 30、8 帧（每方向第 5、6 帧）是 **32** ——
  描边顶到画布最后一行。底边本该由"脚跟着地 + 袍摆"决定，跳下去的是镰刀：柄长 25/26 行，
  而它随持握手泵动 ±2px，泵到底时柄底越过第 28 行，读出来是"镰刀在戳地板"而不是迈步。
  把柄底收短 2 行（`scythe()` 里的 `shaft`，刃、持握手、泵动幅度一个像素没动），
  24 帧底边恒为 30，袍摆下缘在 24..27 之间按波形平移 —— 这才是迈步。
- **`palette` 里查不到红眼**：右视 6 帧的 `inspect` 调色板里没有 `#FF3B30`（`color_count` 10，
  左视 12）—— 兜帽后缘那块 2x6 暗面（`rect(21, y+3, 2, 6, "D")`）与右视的眼睛同列，
  把那双发光红眼整个涂掉了。在 `hood()` 里把这两行交换（暗面先画、眼睛后画），
  右视重新有红眼，`color_count` 10 → 11。
  左视的暗面在脑后（x=9-10），本来就不与眼睛争，所以这个坑只在镜像的那一侧咬人。

其余几条指标本来就是绿的，但断言留在脚本里当护栏：

- **`isolated_pixels` = 0**（24 帧全等）：袍、刃、描边都连通，没有噪点或断线。
  以后加破布、飘带时这条最容易先炸。
- **`near_duplicate_colors` = []**：14 色调色板两两通道差都 > 8，没有该合并的近似色。
- **`coverage` 0.50-0.56**：占满画布，袍摆行波逐列最多差 1px、没有单列凸出的尖牙，
  所以读作布料起伏而不是溶解。

## 没有腿怎么走

死神全身罩袍，读不出迈腿，所以行走靠三件事叠出来：

- **袍摆行波**：下缘每列的底边 `y = 基准 + round(1.0 · sin(0.5x + 2πt))`，
  时间相位按帧推进，波纹就沿袍子横向流动。振幅压到 1px、波长放宽，
  读作布料起伏而不是溶解。
- **整体起伏** `bob`：接触拍下沉 1px。
- **骨脚**：袍下露两点骨色，按 `swing` 反相抬落，是"迈腿"的直接线索。
  两脚永远有一只踩在第 27-28 行，所以底线不动 —— 动的是袍。

镰刀是另一处坑：正/背视里刃必须朝身体**外侧**扫出，向内会横过脸把兜帽盖掉；
侧视里刃朝前扫，靠抛物线下坠 + 由柄向刃尖收薄来铺，比采样圆弧更连续。
逐帧核对过 24 帧的像素：刃口离眼睛最近的那一帧（右视）也还隔着镰柄那两列，从没横过兜帽。
