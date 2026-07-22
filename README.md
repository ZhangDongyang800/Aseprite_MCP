<div align="center">

# 🎨 Aseprite MCP Server

**让 AI 在 Aseprite 中画出像素艺术**

一个 MCP（Model Context Protocol）服务器，让 AI 通过像素级绘制原语在 Aseprite 中创作像素画，读取画布截图并迭代修正，直到画出满意的作品。


[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0%2B-FF6B35?style=flat-square)](https://github.com/jlowin/fastmcp)
[![Aseprite](https://img.shields.io/badge/Aseprite-v1.3%2B-7D9F37?style=flat-square)](https://aseprite.org/)
[![Stars](https://img.shields.io/github/stars/ZhangDongyang800/Aseprite_MCP?style=flat-square&logo=github&color=yellow)](https://github.com/ZhangDongyang800/Aseprite_MCP/stargazers)

<p align="center">
  <a href="README_EN.md">🇺🇸 English</a>
</p>

</div>

<br>

> [!IMPORTANT]
> 本项目需要本地安装 [Aseprite](https://aseprite.org/) v1.3+，AI 通过 MCP 协议调用 Aseprite CLI + Lua 脚本完成绘制。

---

##  目录

- [ 她怎么使用](#-她怎么使用)
- [ 她能做什么](#-她能做什么)
- [ Demo](#-demo)
- [ 欢迎你的参与以及贡献](#-欢迎你的参与以及贡献)
- [ 开源协议](#-开源协议)

---

##  她怎么使用

### 1. 环境准备

在配置 MCP 之前，需要先准备本地开发环境：

| 依赖 | 版本要求 | 下载 |
|------|---------|------|
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) |
| Aseprite | v1.3+ | [aseprite.org](https://aseprite.org/)（需记住安装路径） |

### 2. MCP Server 搭建

```bash
git clone https://github.com/ZhangDongyang800/Aseprite_MCP.git
cd Aseprite_MCP
pip install fastmcp
```

### 3. 客户端配置

> [!IMPORTANT]
> 以下配置中的路径需替换为你本地的实际路径：
> - `args` 中的 `server.py` 路径
> - `ASEPRITE_PATH` 环境变量值
> - `command` 中的 `python` 路径

**TRAE：**

打开 TRAE → 设置 → MCP → 添加 MCP Server，粘贴：

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "python",
      "args": ["C:\\path\\to\\Aseprite_MCP\\server.py"],
      "env": {
        "ASEPRITE_PATH": "C:\\Program Files\\Aseprite\\aseprite.exe"
      }
    }
  }
}
```

**Codex CLI：**

配置文件：`~/.codex/config.toml`

```toml
[mcp_servers.aseprite]
command = "python"
args = ["/path/to/Aseprite_MCP/server.py"]

[mcp_servers.aseprite.env]
ASEPRITE_PATH = "C:\\Program Files\\Aseprite\\aseprite.exe"
```

配置完成后，在 AI 工具中让 AI 使用 Aseprite 相关工具即可开始创作。

---

##  她能做什么

让 AI 像人类画师一样，在 Aseprite 里完整地创作像素画 —— 支持像素级绘制、多图层管理、动画帧编辑、调色板控制、动画标签、图像变换、画布预览的完整工作流，共计 **38 个工具**。

###  像素级绘制

所有绘制工具均支持 `layer` 和 `frame` 参数，可在指定图层和帧上绘制（默认第1图层第1帧）。

| 工具 | 说明 |
|------|------|
| `draw_pixel` | 在指定坐标画一个像素 |
| `draw_line` | 画一条直线 |
| `draw_rect` | 画矩形（支持空心 / 实心） |
| `draw_ellipse` | 画椭圆（支持空心 / 实心） |
| `fill_region` | 油漆桶填充连通区域 |
| `clear_region` | 清除指定区域为透明 |
| `clear_canvas` | 清空整个画布 |

###  精灵管理

| 工具 | 说明 |
|------|------|
| `create_sprite` | 创建新画布（支持 `rgb` / `grayscale` / `indexed` 模式） |
| `open_sprite` | 打开已有的 `.ase` 或 `.png` 文件 |
| `save_sprite` | 保存为 `.ase` / `.png` / `.gif` |
| `close_session` | 关闭会话并清理临时资源 |

###  动画与帧

| 工具 | 说明 |
|------|------|
| `add_frame` | 添加新帧（复制上一帧或创建空白帧） |
| `remove_frame` | 删除指定帧 |
| `set_frame_duration` | 设置帧持续时间（秒） |
| `get_frame_info` | 获取所有帧信息（帧数、每帧时长） |
| `export_gif` | 导出 GIF 动画（支持缩放） |
| `export_sprite_sheet` | 导出精灵表（PNG + JSON 数据） |

###  图层管理

| 工具 | 说明 |
|------|------|
| `add_layer` | 创建新图层 |
| `remove_layer` | 删除图层（按名称或索引） |
| `set_layer_properties` | 设置图层属性（名称、可见性、不透明度、混合模式） |
| `get_layer_info` | 获取所有图层信息 |
| `move_cel` | 在图层/帧之间移动 cel |

###  调色板

| 工具 | 说明 |
|------|------|
| `set_palette_color` | 设置调色板中指定索引的颜色 |
| `get_palette` | 获取当前调色板所有颜色 |
| `resize_palette` | 调整调色板大小（颜色数量） |
| `load_palette` | 从文件加载调色板（`.gpl` / `.pal` / `.png`） |

###  动画标签

| 工具 | 说明 |
|------|------|
| `add_tag` | 创建动画标签（支持播放方向、循环次数） |
| `remove_tag` | 按名称删除标签 |
| `get_tags` | 获取所有标签信息 |

###  图像变换

| 工具 | 说明 |
|------|------|
| `flip_canvas` | 翻转画布（水平 / 垂直） |
| `resize_sprite` | 缩放精灵尺寸 |
| `rotate_canvas` | 旋转画布（90° / 180° / 270°） |
| `crop_sprite` | 裁剪精灵到指定区域 |
| `invert_color` | 反相所有颜色 |
| `replace_color` | 替换指定颜色 |

###  画布检查

| 工具 | 说明 |
|------|------|
| `get_canvas_preview` | 导出 PNG 图片供 AI 视觉分析（**核心迭代工具**） |
| `get_canvas_info` | 获取画布元数据（尺寸、颜色模式等） |
| `get_pixel_color` | 查询指定坐标像素的颜色值 |

###  其他能力

- **MCP Resources** — 会话列表、默认调色板、画布元数据、混合模式列表、动画方向列表
- **MCP Prompts** — 精灵创作引导、迭代审查引导、动画创作引导、多图层工作流引导

> [!TIP]
> `get_canvas_preview` 是整个工作流的核心：AI 画完之后调用它"看"一眼画布，分析后决定是否修正，形成 **绘制 → 预览 → 分析 → 修正** 的闭环。

<br>

<div align="center">

```
AI 请求 → MCP 工具调用 → FastMCP (Python) → Aseprite CLI → Lua 脚本 → .ase 文件
                                                                    ↓
AI 视觉分析 ← base64 PNG ← Image 对象 ← FastMCP ← export_png.lua ←─┘
```

</div>

---

## 🎮 Demo

项目包含一个骑士行走动画示例，展示了 AI 如何通过 Aseprite MCP 创作完整的游戏素材。

**示例：Chibi Knight Walk Cycle**

<div align="center">

**四方向行走动画**

| ↓ 下 | ↑ 上 |
|:---:|:---:|
| ![](demo/Knightling/knight_walk_down.gif) | ![](demo/Knightling/knight_walk_up.gif) |
| ← 左 | → 右 |
| ![](demo/Knightling/knight_walk_left.gif) | ![](demo/Knightling/knight_walk_right.gif) |

**精灵表**

![](demo/Knightling/chibi_knight_spritesheet.png)

</div>

**AI Prompt：**

> 使用 Aseprite MCP，生成像素艺术精灵表，展示一位银色盔甲的勇敢骑士，手持长剑，四方向行走循环（下、上、左、右），每方向 4 帧动画，32x32 大小，扁平色彩，透明背景。



---

## 🤝 欢迎你的参与以及贡献

欢迎提交 [Issue](https://github.com/ZhangDongyang800/Aseprite_MCP/issues) 和 [Pull Request](https://github.com/ZhangDongyang800/Aseprite_MCP/pulls)！

我试用过了，但不能保证她真的很好用，她还需要更多的优化。


---

##  开源协议

本项目基于 [MIT License](LICENSE) 开源。

Copyright © 2026 [ZhangDongyang800](https://github.com/ZhangDongyang800)

<div align="center">

<sub>Built with ❤️ for pixel art lovers</sub>

</div>
