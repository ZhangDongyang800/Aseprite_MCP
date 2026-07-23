<div align="center">

# 🎨 Aseprite MCP Server

**让 AI 在 Aseprite 中绘制像素画**

一个模型上下文协议（MCP）服务器，让 AI 通过像素级绘制原语在 Aseprite 中创建像素画，读取画布截图，并不断迭代直至满意。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0%2B-FF6B35?style=flat-square)](https://github.com/jlowin/fastmcp)
[![Aseprite](https://img.shields.io/badge/Aseprite-v1.3%2B-7D9F37?style=flat-square)](https://aseprite.org/)
[![Stars](https://img.shields.io/github/stars/ZhangDongyang800/Aseprite_MCP?style=flat-square&logo=github&color=yellow)](https://github.com/ZhangDongyang800/Aseprite_MCP/stargazers)

<p align="center">
  <a href="README.md">English</a>
</p>

</div>

<br>

> [!IMPORTANT]
> 本项目需要本地安装 [Aseprite](https://aseprite.org/) v1.3+。AI 通过 MCP 协议调用 Aseprite CLI + Lua 脚本来执行绘制。
>
> 支持两种执行模式：
> - **CLI 模式**（默认）：每次工具调用启动一个无头 Aseprite 进程（`aseprite -b`）。无 UI，状态通过 `.ase` 文件传递。
> - **实时模式**（WebSocket）：AI 通过 WebSocket 桥接直接操作正在运行的 Aseprite 实例。UI 可见，状态持久化，你可以实时观看 AI 绘制过程。详见下方的[实时模式配置](#-实时模式可选-websocket)。


---

##  目录

- [ 如何使用](#-如何使用)
- [ 实时模式（可选，WebSocket）](#-实时模式可选-websocket)
- [ 功能介绍](#-功能介绍)
- [ 示例演示](#-示例演示)
- [ 参与贡献](#-参与贡献)
- [ 开源协议](#-开源协议)

---

##  如何使用

### 1. 环境准备

配置 MCP 之前，请先准备好本地开发环境：

| 依赖 | 版本 | 下载 |
|------------|---------|----------|
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) |
| Aseprite | v1.3+ | [aseprite.org](https://aseprite.org/)（请记住安装路径） |

### 2. MCP 服务器安装

```bash
git clone https://github.com/ZhangDongyang800/Aseprite_MCP.git
cd Aseprite_MCP
pip install -e .
```

这将安装 `fastmcp` 和 `websockets`（后者用于可选的[实时模式](#-实时模式可选-websocket)）。

### 3. 客户端配置

> [!IMPORTANT]
> 请将以下路径替换为你本地的真实路径：
> - `args` 中的 `server.py` 路径
> - `ASEPRITE_PATH` 环境变量的值
> - `command` 中的 `python` 路径

**TRAE：**

打开 TRAE → 设置 → MCP → 添加 MCP 服务器，粘贴：

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

**Codex CLI:**

配置文件：`~/.codex/config.toml`

```toml
[mcp_servers.aseprite]
command = "python"
args = ["/path/to/Aseprite_MCP/server.py"]

[mcp_servers.aseprite.env]
ASEPRITE_PATH = "C:\\Program Files\\Aseprite\\aseprite.exe"
```

配置完成后，让 AI 工具使用 Aseprite 相关工具即可开始创作。

---

## 🎥 实时模式（可选，WebSocket）

实时模式让 AI 直接操作你**正在运行的 Aseprite 实例**——你可以在屏幕上实时观看每一笔的绘制过程，且精灵状态在工具调用间持久化（无需反复打开/保存文件）。

### 工作原理

```
┌─────────┐    MCP (stdio)    ┌──────────────┐   WebSocket    ┌──────────────────┐
│  AI/TRAE │ ───────────────► │ Python MCP   │ ─────────────► │ Aseprite 扩展     │
│          │ ◄─────────────── │ 服务器        │ ◄──────────── │ (WebSocket 客户端) │
└─────────┘                   └──────────────┘                └──────┬───────────┘
                                                                     │ Lua app.* API
                                                                     ▼
                                                              ┌──────────────┐
                                                              │ 可见的 Aseprite  │
                                                              │ 精灵 + UI       │
                                                              └──────────────┘
```

Python MCP 服务器在 `127.0.0.1:9001` 启动一个 WebSocket 服务器。Aseprite 扩展作为客户端连接到它。每次 MCP 工具调用都会通过 WebSocket 转发到 Aseprite，通过现有的 Lua 脚本执行，并将结果返回。

### 配置步骤

**1. 安装 Aseprite 扩展**

扩展位于本仓库的 `extension/` 文件夹中。通过以下方式安装：

- 打开 Aseprite → `File > Scripts > Open Scripts Folder`
- 将 `extension/` 文件夹的全部内容复制到脚本文件夹中（或使用 `Edit > Preferences > Extensions > Add Extension` 并选择 `extension/` 文件夹）

**2. 在 MCP 配置中启用 WebSocket 模式**

在 MCP 服务器配置的 `env` 部分添加 `ASEPRITE_MCP_MODE=ws`：

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "python",
      "args": ["C:\\path\\to\\Aseprite_MCP\\server.py"],
      "env": {
        "ASEPRITE_PATH": "C:\\Program Files\\Aseprite\\aseprite.exe",
        "ASEPRITE_MCP_MODE": "ws",
        "ASEPRITE_WS_HOST": "127.0.0.1",
        "ASEPRITE_WS_PORT": "9001"
      }
    }
  }
}
```

**3. 连接 Aseprite**

MCP 服务器运行后，打开 Aseprite 并点击：

`File > Scripts > MCP Bridge: Toggle Connection`

你将看到提示："MCP Bridge: Connected to ws://127.0.0.1:9001"。

现在 AI 可以直接操作 Aseprite——创建精灵、绘制像素，你会看到它实时发生。

### CLI 模式与实时模式对比

| 方面 | CLI 模式（默认） | 实时模式（WebSocket） |
|--------|-------------------|----------------------|
| UI 可见性 | 无头模式（`-b` 标志） | 完整 UI，可观看 AI 绘制 |
| 状态持久化 | 每次调用独立（基于文件） | 跨调用持久化 |
| 启动开销 | 每次调用启动新进程 | 单个运行实例 |
| 配置复杂度 | 无需配置 | 需安装扩展并连接 |
| 需要 Aseprite 焦点 | 否 | 是（未聚焦时回调会延迟） |
| 回退 | 不适用 | 扩展未连接时自动回退到 CLI |

> [!TIP]
> 如果 Aseprite 扩展未连接，实时模式工具会返回清晰的错误信息引导你连接。现有的 CLI 模式始终可用作回退，只需设置 `ASEPRITE_MCP_MODE=cli`（或删除该变量）。

### 环境变量

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `ASEPRITE_MCP_MODE` | `cli` | 执行模式：`cli` 或 `ws` |
| `ASEPRITE_WS_HOST` | `127.0.0.1` | WebSocket 服务器绑定地址 |
| `ASEPRITE_WS_PORT` | `9001` | WebSocket 服务器端口 |

---

##  功能介绍

让 AI 像人类画师一样在 Aseprite 中创作像素画——支持完整的工作流，包括像素级绘制、多图层管理、动画帧编辑、调色板控制、动画标签、图像变换和画布预览。共 **49 个工具**。

###  像素级绘制

所有绘制工具都支持 `layer` 和 `frame` 参数，可在指定图层和帧上绘制（默认：图层 1，帧 1）。

| 工具 | 说明 |
|------|-------------|
| `draw_pixel` | 在指定坐标绘制一个像素 |
| `draw_line` | 绘制一条直线 |
| `draw_rect` | 绘制矩形（描边 / 填充） |
| `draw_ellipse` | 绘制椭圆（描边 / 填充） |
| `fill_region` | 油漆桶填充连通区域 |
| `clear_region` | 清除区域为透明 |
| `clear_canvas` | 清空整个画布 |

###  精灵管理

| 工具 | 说明 |
|------|-------------|
| `create_sprite` | 创建新画布（支持 `rgb` / `grayscale` / `indexed` 模式） |
| `open_sprite` | 打开已有的 `.ase` 或 `.png` 文件 |
| `save_sprite` | 保存为 `.ase` / `.png` / `.gif` |
| `close_session` | 关闭会话并清理临时资源 |
| `import_png` | ★推荐★ 从 PNG 文件导入图像——画任意图形的最省 token 方式。两种模式：`new`（从 PNG 创建新会话，自动读取真实尺寸）/ `stamp`（将 PNG 贴到已有会话的指定图层/帧/偏移位置）。推荐工作流：用 Python/PIL 生成 PNG，调用 `import_png(mode="new")` 导入，再用 `draw_pixel` / `draw_rect` 等精修。 |

###  动画与帧

| 工具 | 说明 |
|------|-------------|
| `add_frame` | 添加新帧（复制上一帧或创建空帧） |
| `remove_frame` | 删除指定帧 |
| `set_frame_duration` | 设置帧持续时间（秒） |
| `get_frame_info` | 获取所有帧信息（数量、每帧时长） |
| `export_gif` | 导出 GIF 动画（支持缩放） |
| `export_sprite_sheet` | 导出精灵表（PNG + JSON 数据） |

###  图层管理

| 工具 | 说明 |
|------|-------------|
| `add_layer` | 创建新图层 |
| `remove_layer` | 删除图层（按名称或索引） |
| `set_layer_properties` | 设置图层属性（名称、可见性、不透明度、混合模式） |
| `get_layer_info` | 获取所有图层信息 |
| `move_cel` | 在图层/帧之间移动 cel |

###  调色板

| 工具 | 说明 |
|------|-------------|
| `set_palette_color` | 设置指定调色板索引处的颜色 |
| `get_palette` | 获取当前调色板的所有颜色 |
| `resize_palette` | 调整调色板大小（颜色数量） |
| `load_palette` | 从文件加载调色板（`.gpl` / `.pal` / `.png`） |

###  动画标签

| 工具 | 说明 |
|------|-------------|
| `add_tag` | 创建动画标签（支持播放方向、循环次数） |
| `remove_tag` | 按名称删除标签 |
| `get_tags` | 获取所有标签信息 |

###  图像变换

| 工具 | 说明 |
|------|-------------|
| `flip_canvas` | 翻转画布（水平 / 垂直） |
| `resize_sprite` | 调整精灵尺寸 |
| `rotate_canvas` | 旋转画布（90° / 180° / 270°） |
| `crop_sprite` | 将精灵裁剪到指定区域 |
| `invert_color` | 反转所有颜色 |
| `replace_color` | 替换指定颜色 |

###  调色板增强

| 工具 | 说明 |
|------|-------------|
| `apply_preset_palette` | ★批量★ 应用内置预设调色板（db16/db32/aap64/nes/gameboy） |
| `derive_shading_palette` | 从基础色派生三阶阴影调色板（含色相偏移，默认自动应用） |
| `append_palette_colors` | ★批量★ 向调色板追加多个颜色 |

###  动画辅助

| 工具 | 说明 |
|------|-------------|
| `apply_timing_preset` | ★批量★ 按动画类型批量设置帧持续时间 |
| `draw_animation_frames` | ★批量★ 一次调用绘制多个动画帧 |
| `export_onion_skin_preview` | 洋葱皮叠加预览（对比相邻帧） |

###  瓦片集工具

| 工具 | 说明 |
|------|-------------|
| `create_tileset_canvas` | 创建瓦片集画布并设置网格 |
| `export_tiled_preview` | 平铺布局预览（接缝检查） |

###  质量检查

| 工具 | 说明 |
|------|-------------|
| `export_silhouette` | 导出纯黑剪影（剪影测试） |
| `check_canvas_standards` | 自动检查画布标准（尺寸 / 颜色 / 帧时长 / 像素画规范） |

###  画布检查

| 工具 | 说明 |
|------|-------------|
| `get_canvas_preview` | 导出 PNG 供 AI 视觉分析（**核心迭代工具**） |
| `get_canvas_info` | 获取画布元数据（尺寸、颜色模式等） |
| `get_pixel_color` | 查询指定坐标处像素的颜色 |

###  其他能力

- **MCP 资源** — 会话列表、默认调色板、画布元数据、混合模式列表、动画方向列表
- **MCP 提示词** — 精灵创建指南、迭代审查指南、动画创建指南、多图层工作流指南

> [!TIP]
> `get_canvas_preview` 是工作流的核心：绘制后，AI 调用它来"看到"画布、分析它，并决定是否修正，形成 **绘制 → 预览 → 分析 → 修正** 的循环。

<br>

<div align="center">

**CLI 模式数据流**（默认）

```
AI 请求 → MCP 工具调用 → FastMCP (Python) → Aseprite CLI → Lua 脚本 → .ase 文件
                                                                    ↓
AI 视觉分析 ← base64 PNG ← Image 对象 ← FastMCP ← export_png.lua ←─┘
```

</div>

---

##  示例演示



**示例：Q 版骑士行走动画**

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

**AI 提示词：**

> 使用 Aseprite MCP 生成一个勇敢骑士的像素画精灵表，银色盔甲手持长剑。四方向行走动画（下、上、左、右），每个方向 4 帧，32x32，平涂色块，透明背景。

---

**示例：导入 PNG（画任意图形的推荐工作流）**

绘制复杂或不适合网格的图形时，用 Python/PIL 生成 PNG 再导入，比用 `draw_from_grid` 描述每个像素或调用数百次 `draw_pixel` 要省得多得多的 token。

```python
# 第 1 步：用 Python/PIL 生成 PNG
from PIL import Image, ImageDraw
img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))      # 透明背景
d = ImageDraw.Draw(img)
d.ellipse([4, 4, 27, 27], fill=(231, 76, 60, 255))    # 画一个红色圆
img.save("circle.png")
```

```python
# 第 2 步：将 PNG 导入为新的 Aseprite 会话
import_png(png_path="circle.png", mode="new")
# 返回：{ "session_id": "...", "width": 32, "height": 32, ... }
```

```python
# 第 3 步：如需精修，使用像素级工具
draw_pixel(session_id="...", x=16, y=6, color="#FFFFFF")   # 添加高光
```

使用 `mode="stamp"` 可将 PNG 贴到已有会话的指定图层/帧/偏移位置——适合添加细节、贴图章或合成子图。


---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

我已尝试过，但无法保证完美运行。仍需更多优化。

---

##  开源协议

本项目基于 [MIT License](LICENSE) 开源。

Copyright © 2026 [ZhangDongyang800](https://github.com/ZhangDongyang800)

<div align="center">

<sub>用 ❤️ 为像素画爱好者而建</sub>

</div>
