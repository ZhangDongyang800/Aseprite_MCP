# Q版草原 tileset 生成器

32x32 像素瓦片，32 张，8x4 无缝图集（256x128）；水面 4 帧循环动画；
外加一张 12x8 瓦片拼出的示例场景（384x256）。Q版 = 圆角团块 + 三档明度 + 亮部左上。

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py       # 建会话 -> 一批 ops 画完 -> 逐像素校验 -> 打包
python grassland_q.py   # 不碰 Aseprite，只看像素矩阵
```

产物写到上级 `demo/grassland_q/`：

| 文件 | 说明 |
| --- | --- |
| `grassland_q_tileset.png` | 256x128 图集，第 1 帧（静态首帧，水面相位 0） |
| `grassland_q_preview.png` | 4x 放大 + 分隔线 + 槽位名标注，给人看的 |
| `grassland_q_scene.png` | 384x256 场景，按 2x 导出便于查看 |
| `grassland_q_water.gif` | 水面瓦片 4x、4 帧循环 |
| `grassland_q_tileset.ase` | 4 帧 + `water_loop` 标签（`*.ase` 在 .gitignore 里，本地生成） |
| `grassland_q_scene.ase` | 场景单帧文档（同上，不入库） |

中间产物在 `.build/`（已 gitignore）。

## 画这张图只用了 v2 工具面

- 图集 8 个 op 一个原子批量画完（`create_sprite` / `add_frames` / 4x `paint_grid` /
  `set_durations` / `add_tag` / `save_sprite`）= 一次 Aseprite 进程，实测约 0.45s、零警告。
- 网格文件写在**会话工作目录**里，所以 `paint_grid` 不用 `confirmed=true` ——
  见 `AGENTS.md` 的门闩约定：文件在工作目录内即视为可信输入。
- `run_lua` 只用来导出 PNG（工具面没有 export op，属于正当的逃逸舱用途）。
  多帧文档上 `saveCopyAs` 会写成 `x1.png…xN.png`，所以按 `inspect.lua` 的老办法，
  先 `Sprite(s)` 拷出临时文档再压成单帧导出，原文档帧数不受影响。

同一张图用「已连接的 MCP 手动画」和「`produce.py` 无头跑一遍」各画了一次，
导出的 5 张 PNG **逐字节相同**（见 `q_crosscheck.py` 的做法），所以两条路径等价。

## 校验不是"没报错"

`produce.py` 的 `verify()` 把导出的 PNG 和 Python 侧的设计矩阵逐像素比对
（图集 4 帧 + 场景），全绿才打包；同时断言水面 4 帧两两不同 ——
否则 GIF 编码器会把相同帧合并掉，循环动画就只剩一帧。

## Q版像素美术的几条硬规矩

- **圆优先**：实体全部用圆角椭圆叠加（`_disc` + `_ring` 勾一圈暗边），
  可爱感来自轮廓的圆钝，不是来自加描边。
- **每种材质只有三档明度**（base / shade / light）+ 少量高亮点。
  高频抖动是"写实"的敌人，也是 Q版显得脏的元凶 —— 草地用 2x2 色块，水面用断续波线。
- **每张瓦片必须有一个焦点**：一朵花就是一朵能认出来的花（5px 花瓣盘 + 1px 花心 +
  短茎），缩小之后还认得出才算合格。
- **渐变属于地形，不属于水**：水面瓦片是**均匀**的一档蓝。曾经给每张水瓦片画
  "底部渐深"，铺成池塘后每 32px 就重复一次，整片水域出现横向条带。
- **过渡砖**：路径 / 水域 / 麦田与草地相接处都有专门的过渡瓦片，缺了这套砖，
  地图就是硬边方块。
- **场景按位置错开相位**：`scene()` 给带动画的瓦片传 `(tx + ty) % 4`。
- **路的宽度控制在 2 格**：铺到 3-4 格宽就不像路，而像一块空地。