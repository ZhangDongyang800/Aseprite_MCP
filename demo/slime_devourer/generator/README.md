# slime_devourer 生成器

这个 demo 不是一次性手画的，而是参数化生成后通过 MCP 落到 Aseprite 的。按顺序跑：

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe   # 不设则依赖自动检测
python monster.py                 # 打印 20 帧 ASCII，调形用
python preview.py 6               # 本地接触表 .build/sheet_preview.png（不启动 Aseprite）
python build_monster.py           # 建会话 -> run_lua 建结构 -> 4 批像素 -> 导出
python finalize.py                # 修帧时长 + 逐帧像素比对 Aseprite 落盘结果
python make_demo.py               # 把 .build 产物打包成上级目录里的 gif / 精灵表 / .ase
```

中间产物都在 `.build/`（已 gitignore）：`monster.ase`、`monster_sheet.png`、
`monster_data.json`、`frames/frame1..20.png`。

## 职责边界

- **像素**：全部由 `apply_operations` 的 `draw_rect` 批次写入（4 批共 3248 个 op，
  每批一个方向 5 帧）。同色水平连续段会合并成一个 op。
- **结构**：`run_lua` 只做 op 注册表里没有的能力——加帧、设帧时长、建 tag、
  导出精灵表。op 面无法扩帧（`frame=2` 会报 `frame index out of bounds`），
  所以动画结构必须走逃逸舱。
- 修改造型只需要动 `monster.py` 里的 `SIDE_CFG` / `FRONT_CFG` 与 mask 构造函数，
  重跑后两条即可。

## 造型模型

侧视用「颅骨椭圆 + 下颚椭圆绕嘴角铰点反向旋转」：张嘴时上颚抬起、下颚落下，
中间楔形即口腔，所以嘴是咬穿轮廓的缺口而不是体内的一个洞。几何只产出语义
mask，明暗与描边在渲染阶段统一计算，因此 `right` 只是 `left` 的 mask 水平镜像，
光照仍固定在左上。
