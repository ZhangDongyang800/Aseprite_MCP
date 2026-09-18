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
- [工具](#工具)
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
| `ASEPRITE_PATH` | 自动检测 | Aseprite 可执行文件路径（优先于 `PATH` 与常见安装位置的自动检测） |
| `ASEPRITE_MCP_MODE` | `cli` | 执行模式：`cli` 或 `ws` |
| `ASEPRITE_WS_HOST` | `127.0.0.1` | WebSocket 服务器绑定地址 |
| `ASEPRITE_WS_PORT` | `9001` | WebSocket 服务器端口 |

---

## 工具

服务器只暴露三个 MCP 工具：

| 工具 | 说明 |
|------|------|
| `apply_operations` | 在单个事务中执行一批 op——唯一的变更入口。传入 `session_id` + `ops[]`；`dry_run=true` 只校验、不产生副作用；批次包含破坏性 op（`clear_canvas`、`close_session`）时必须传 `confirmed=true`。省略 `session_id` 且首个 op 为 `create_sprite` / `open_sprite` 时会自动创建会话。 |
| `inspect` | 只读感知：返回画布预览图与量化指标（调色板、颜色数、包围盒、覆盖率、半透明与孤立像素）。永不修改文档。 |
| `run_lua` | 逃逸舱：执行任意 Lua。需要 `unsafe=true` 且 `confirmed=true`。 |

op 是注册在 `src/v2/ops/` 中的命名操作（Pydantic 参数模型），其 Lua 实现位于 `scripts/ops_*.lua`。内置 op：`create_sprite`、`open_sprite`、`save_sprite`、`close_session`、`draw_pixel`、`draw_rect`、`fill_region`、`clear_canvas`。

```python
apply_operations(ops=[
    {"op": "create_sprite", "width": 32, "height": 32},
    {"op": "draw_rect", "x": 4, "y": 4, "width": 24, "height": 24, "color": "#E74C3C", "filled": True},
    {"op": "draw_pixel", "x": 16, "y": 6, "color": "#FFFFFF"},
])
```

所有绘制 op 都接受 `layer` / `frame`（从 1 开始计数，默认 1/1）。一批 op 在单个 `app.transaction` 中执行，因此默认的 `atomic=true` 会在任意 op 失败时回滚整批。

> [!TIP]
> `inspect` 是工作流的核心：绘制后，AI 调用它来"看到"画布、分析它，并决定是否修正，形成 **操作 → 检查 → 分析 → 修正** 的循环。

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
