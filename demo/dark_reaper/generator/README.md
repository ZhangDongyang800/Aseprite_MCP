# dark_reaper 生成器

32x32 暗黑死神，4 方向 x 6 帧行走循环。

```bash
export ASEPRITE_PATH=/path/to/aseprite.exe
python produce.py          # 建会话 -> run_lua 建结构 -> 4 批像素 -> 逐帧校验 -> 打包
python reaper.py           # 只看 ASCII
```

产物写到上级 `demo/dark_reaper/`：`dark_reaper_walk_{down,left,right,up}.gif`（4x）、
`dark_reaper_spritesheet.png`（192x128）、`dark_reaper_walk.ase`（24 帧 + 4 个
`walk_*` tag）。中间产物在 `.build/`（已 gitignore）。

## 没有腿怎么走

死神全身罩袍，读不出迈腿，所以行走靠三件事叠出来：

- **袍摆行波**：下缘每列的底边 `y = 基准 + round(1.0 · sin(0.5x + 2πt))`，
  时间相位按帧推进，波纹就沿袍子横向流动。振幅压到 1px、波长放宽，
  读作布料起伏而不是溶解。
- **整体起伏** `bob`：接触拍下沉 1px。
- **骨脚**：袍下露两点骨色，按 `swing` 反相抬落，是"迈腿"的直接线索。

镰刀是另一处坑：正/背视里刃必须朝身体**外侧**扫出，向内会横过脸把兜帽盖掉；
侧视里刃朝前扫，靠抛物线下坠 + 由柄向刃尖收薄来铺，比采样圆弧更连续。
