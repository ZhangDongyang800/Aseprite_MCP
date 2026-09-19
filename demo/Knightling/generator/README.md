# Knightling 生成器

32x32 Q 版骑士，4 方向 x 6 帧行走循环。

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py          # 建会话 -> run_lua 建结构 -> 4 批像素 -> 逐帧校验 -> 打包
python knight.py           # 只看 ASCII
```

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

`build(direction, frame)` 返回一张字符网格，`ops_for()` 把同色水平连续段合并成
`draw_rect`，所以一帧只有几十个 op、整批 24 帧约 3700 个 op。
