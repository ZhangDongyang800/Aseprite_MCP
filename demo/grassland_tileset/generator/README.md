# 草原 tileset 生成器

32x32 像素瓦片，32 张，8x4 无缝图集；水面 4 帧循环动画；外加一张 12x8 瓦片拼出的示例场景。

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py       # 建会话 -> 一批 ops 画完 -> 逐像素校验 -> 打包
python grassland.py     # 不碰 Aseprite，只看像素矩阵
```

产物写到上级 `demo/grassland_tileset/`：

| 文件 | 说明 |
| --- | --- |
| `grassland_tileset.png` | 256x128 图集，第 1 帧（静态首帧，水面相位 0） |
| `grassland_tileset_preview.png` | 4x 放大 + 分隔线 + 槽位名，给人看的 |
| `grassland_scene.png` | 384x256 场景，按 2x 导出便于查看 |
| `grassland_water_loop.gif` | 水面瓦片 4x、4 帧循环 |
| `grassland_tileset.ase` | 4 帧 + `water_loop` 标签，帧 2-4 是水面动画（`*.ase` 在 .gitignore 里，本地生成） |
| `grassland_scene.ase` | 场景单帧文档（同上，不入库） |

中间产物在 `.build/`（已 gitignore）。

## 只用了 v2 工具面

- 图集 8 个 op 一个原子批量画完（`create_sprite` / `add_frames` / 4x `paint_grid` /
  `set_durations` / `add_tag` / `save_sprite`）= 一次 Aseprite 进程，实测约 0.5s。
- 网格文件写在**会话工作目录**里（`<work>/sessions/<uuid>/`），所以 `paint_grid`
  不用 `confirmed=true` —— 见 `AGENTS.md` 里的门闩约定：文件在工作目录内即视为可信输入。
- `run_lua` 只用来导出 PNG：工具面没有 export op，这属于正当的逃逸舱用途。
  多帧文档上 `saveCopyAs` 会写成 `name1.png…nameN.png`，所以按 `inspect.lua` 的老办法，
  先 `Sprite(s)` 拷贝出临时文档再压成单帧导出，原文档帧数不受影响。

## 校验不是"没报错"

`produce.py` 的 `verify()` 把导出的 PNG 和 Python 侧的设计矩阵逐像素比对
（图集 4 帧 + 场景），全绿才打包；同时断言水面 4 帧两两不同 ——
否则 GIF 编码器会把相同帧合并掉，循环动画就只剩一帧。

## 像素美术上的几条硬规矩

- **过渡砖**：路径/水域/麦田与草地相接处都有专门的过渡瓦片（`*_edge_*` + `*_corner_*`），
  拼出来才是圆角、才是沙滩；缺了这套砖，地图就是硬边方块。
- **平铺无缝**：纹理由 `(x, y)` 的坐标哈希决定，没有依赖边界的画法，
  所以同一张瓦片重复多少次都看不出接缝。
- **克制的噪点**：草地用 2x2 色块抖动，水面用 1px 断续短划；两者都刻意压密度，
  否则 32px 瓦片在大面积铺开时就是一片雪花。
- **沙水过渡不用棋盘抖动**：沙和水互相对抖会产生橙蓝高频噪点，看着像脏边；
  `water_edge_*` 单独实现：实心沙带 -> 两色抖动 -> 边界一条断续浪花。
- **光源左上**：所有亮面判定都是 `(x < cx and y < cy) or (x - cx + y - cy) < -k`。
- **场景按位置错开相位**：`scene()` 给带动画的瓦片传 `(tx + ty) % 4`，
  否则一片池塘就是同一张水面贴图盖 20 次。