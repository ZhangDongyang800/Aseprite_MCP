# Knightling 生成器

32x32 Q 版骑士，4 方向 x 6 帧行走循环。

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py          # 建会话 -> 一次原子批量（结构+24 帧）-> inspect 质检 -> 逐帧校验 -> 打包
python knight.py           # 只看 ASCII
python knight.py --sheet   # 本地接触表 .build/knight_sheet.png
```

`produce.py` 把服务器的工作目录钉在 `.build/work`（`ASEPRITE_WORK_DIR`）：这条路径必须
是纯 ASCII，否则 Aseprite 会抛出误导性的"lua 引擎缺失"；中间产物也因此不会跑到仓库的
`work/` 里去。

产物写到上级 `demo/Knightling/`：`knight_walk_{down,left,right,up}.gif`（4x，128x128）、
`chibi_knight_spritesheet.png`（192x128）、`chibi_knight_walk.ase`（24 帧 + 4 个
`walk_*` tag）。中间产物在 `.build/`（已 gitignore）。

## 行走是怎么来的

`knight.py` 里每个部件都是相位 `t = i / 6` 的函数，共享三条通道：

- `swing = sin(2πt)`：两条腿反相，正=这条腿在前；手臂与剑反相跟随。
- `bob = round(|swing|)`：接触拍身体下沉 1px，过渡拍回到位。
- `sway = round(2·swing)`：披风与盔缨甩动，越靠下摆幅度越大。

摆幅刻意放大（腿部正视抬 2px、侧视前后 4px），因为素材最终按 4x 显示，
1px 的动作在那个尺寸下读不出来。剑整体平移而非只动护手，否则剑会被拉长。

`build(direction, frame)` 返回一张字符网格，`grid_lua()` 把它序列化成 `paint_grid`
吃的 Lua 数据文件（`palette` + `rows`，`.` 是透明跳过）。

## 怎么画进 Aseprite

只用 v2 工具面。结构与像素收进**一次** `apply_operations` 原子批量 = 一次 Aseprite 进程；
`create_sprite` 只能单独一次调用，因为网格文件要写进它才分配到的会话目录：

| 用途 | op | 数量 |
|---|---|---|
| 建文档 | `create_sprite`（单独一次调用，拿 session_id） | 1 |
| 扩到 24 帧 | `add_frames{count=23, duration=0.12}` | 1 |
| 像素 | `paint_grid{path, frame}`，**每帧一个** | 24 |
| 逐帧时长 | `set_durations{durations=[0.12 x 24]}` | 1 |
| 四个方向的动画标签 | `add_tag{walk_down/left/right/up}` | 4 |
| 存 .ase | `save_sprite` | 1 |
|  | **合计** | **31 ops，一次批量 ≈0.4s** |

24 个网格文件写进 `<.build>/work/sessions/<session_id>/`——会话工作目录之内，
所以 `paint_grid` 免 `confirmed=true`。`run_lua` 只剩一件工具面没有能力的事：
导出精灵表（`app.command.ExportSpriteSheet`）和 GIF 源帧（`saveCopyAs` 在多帧文档上
写成 `frame1.png..frame24.png`，正是这里要的文件名）。

## 美术质检（produce.py 里的 `quality()`）

24 帧逐帧调 `inspect` 读 `metrics`，任何一条不达标就打印 `FAIL:` 并非零退出：

- `isolated_pixels == 0`：没有孤立像素（噪点/描边断裂）。
- `near_duplicate_colors == []`：调色板 11 色里没有被指标判为"肉眼几乎分不出"的色对
  （最接近的一对是亮银 `s` 与高光 `w`，三通道差 24/21/16，而指标阈值是每通道 ≤8），
  所以无需收敛配色。
- `bbox` 底边恒为第 28 行：24 帧脚底基线不漂移；顶边在第 0/1 行之间跳，那是 `bob`
  的接触拍下沉，属于行走本身。
- `coverage` 换算成不透明像素数后与 `knight.py` 的模型逐帧相等（防"op 报成功但像素没落"），
  并且左右两向同相位帧的像素数必须完全相同。
- `semi_transparent_pixels == 0`、`color_count <= 11`、24 帧时长一致、4 个 tag 齐全。

指标暴露出来并已修掉的缺陷（都在 `knight.py` 的模型里，造型与配色未变）：

1. **右向体积比左向大**：左右两向本该是镜像轮廓，实测第 3 帧 401 px vs 408 px。
   根因是侧向部件的 x 常量直接照抄左向而没有镜像：腿摆轴 13（右向应为 14）、
   胸甲高光 18..20（镜像是 19..21）、持剑手 15..17（镜像是 16..18）、盔体 12..20
   （镜像是 13..21）、盔缨 15+sw（镜像是 14+sw）。逐条改完后 6 对左右帧的像素数
   两两相等（428/411/401/400/433/448），bbox 宽度也一致。
2. **右向观察缝被剑刃吃掉半条**：缝画在 20..23，而剑刃占 22..23 且后画，于是右向的
   黑缝只剩 2px 宽（左向是 4px）。缝移到 18..21（左向 10..13 的镜像位）后两向一致。
3. **右向护手不居中于剑刃**：`x-1 if left else x` 让右向护手只往右出 2px、往左出 0px，
   整把剑视觉偏右。统一成 `x-1` 后两侧各出 1px，正好是左向的镜像。
4. **正/背视腿组偏右 1px**：腿在 12..15 与 17..20（组中心 16），躯干是 10..21
   （中心 15.5）。改成 11..14 与 16..19 后腿组与躯干、头盔、腰带共用同一根中轴。

## 帧时长的单位（这里曾写错过结论）

`set_durations` 与 `add_frames{duration}` 的入参是**秒**，Aseprite 的 `Frame.duration`
在 Lua 接口上**也是秒**，所以 `.ase` 里的 12 帧循环按 0.12s/帧正常播放 —— 本节此前根据
"Aseprite 内部按毫秒存"推断出"`.ase` 近乎瞬时播放"，那是错的：内部单位不等于接口单位。

实测口径：`0.1 / 0.2 / 0.3` 秒经 `saveCopyAs` 导出的 GIF 延时正是 `100 / 200 / 300` ms，
这条已经钉进 `tests/v2/test_e2e_v2.py::test_duration_unit_survives_into_an_exported_gif`。
四个 `knight_walk_*.gif` 的 120ms/帧由打包脚本写入，与 `.ase` 各走各的，两者一致。
