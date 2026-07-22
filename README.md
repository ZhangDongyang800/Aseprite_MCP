# Aseprite MCP Server

一个 MCP（Model Context Protocol）服务器，允许 AI（如 Claude）通过像素级绘制原语在 Aseprite 中创建像素艺术精灵，读取画布图片并迭代修正直到满意。

## 核心功能

- **像素级绘制原语**：draw_pixel, draw_line, draw_rect, draw_ellipse, fill_region, clear_region, clear_canvas
- **精灵管理**：create_sprite, open_sprite, save_sprite, close_session
- **画布检查**：get_canvas_preview（返回 PNG 图片供 AI 视觉分析）, get_canvas_info, get_pixel_color
- **MCP Resources**：会话列表、默认调色板、画布元数据
- **MCP Prompts**：精灵创作引导、迭代审查引导

## 工作原理

```
AI 请求 → MCP 工具调用 → Python (FastMCP) → subprocess → Aseprite CLI → Lua 脚本 → .ase 文件
                                                                    ↓
AI 视觉分析 ← base64 PNG ← Image 对象 ← FastMCP ← export_png.lua ←─────┘
```

1. AI 调用 `create_sprite` 创建画布，获得 `session_id`
2. AI 调用绘制工具（draw_pixel 等）在画布上绘制
3. AI 调用 `get_canvas_preview` 获取画布 PNG 图片
4. AI 分析图片，判断是否需要修正
5. 重复 2-4 直到满意
6. AI 调用 `save_sprite` 保存最终结果

## 安装

### 前置条件

- **Python 3.10+**：[下载地址](https://www.python.org/downloads/)
- **Aseprite v1.3+**：[官网](https://aseprite.org/)，需能通过命令行访问（记住安装路径）

### 安装步骤

```bash
# 1. 克隆项目（或下载 ZIP 解压）
git clone <repository-url>
cd Aseprite_mcp

# 2. 安装依赖
pip install fastmcp pytest pytest-asyncio
```

### 配置 Aseprite 路径

MCP 服务器需要知道 Aseprite 的安装位置。有三种方式（任选其一）：

**方式一：环境变量（推荐）**

```bash
# Windows PowerShell
$env:ASEPRITE_PATH = "C:\Program Files\Aseprite\aseprite.exe"

# Linux / macOS
export ASEPRITE_PATH="/usr/bin/aseprite"
```

**方式二：修改默认值**

编辑 `src/config.py`，将 `ASEPRITE_PATH` 的默认值改为你的路径。

**方式三：配置文件中传递环境变量**（见下方各工具配置示例）

### 完整环境变量

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `ASEPRITE_PATH` | `D:\cxdownload\...\aseprite.exe` | Aseprite 可执行文件路径 |
| `ASEPRITE_WORK_DIR` | `./work` | 会话工作目录（临时文件存放处） |
| `ASEPRITE_SESSION_TIMEOUT` | `3600` | 会话超时时间（秒） |

## 在 AI 工具中配置

MCP 服务器的核心是让 AI 工具能调用它。以下是三大主流工具的配置方法。

### Claude Desktop（桌面应用）

**配置文件位置**：
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Settings/Claude/claude_desktop_config.json`

**打开方式**：Claude Desktop → 设置 → Developer → Edit Config

**配置内容**：

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "python",
      "args": ["C:\\path\\to\\Aseprite_mcp\\server.py"],
      "env": {
        "ASEPRITE_PATH": "C:\\Program Files\\Aseprite\\aseprite.exe"
      }
    }
  }
}
```

> Windows 注意：路径中的反斜杠要双写 `\\`，或使用正斜杠 `/`。

### Claude Code（CLI 工具）

使用命令行添加（最简单）：

```bash
# 添加 MCP 服务器
claude mcp add aseprite -- python /path/to/Aseprite_mcp/server.py

# 带环境变量添加
claude mcp add aseprite -e ASEPRITE_PATH="C:\Program Files\Aseprite\aseprite.exe" -- python /path/to/Aseprite_mcp/server.py

# 查看已配置的服务器
claude mcp list

# 删除服务器
claude mcp remove aseprite
```

### TRAE IDE

**配置方式一：UI 界面（推荐）**

1. 打开 TRAE → 右上角 AI 侧栏 → 设置图标 → MCP
2. 点击"添加 MCP Server"或"手动配置"
3. 粘贴下方 JSON 配置

**配置方式二：编辑配置文件**

配置文件位置：项目根目录 `.trae/mcp.json` 或全局配置

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "python",
      "args": ["C:\\path\\to\\Aseprite_mcp\\server.py"],
      "env": {
        "ASEPRITE_PATH": "C:\\Program Files\\Aseprite\\aseprite.exe"
      }
    }
  }
}
```

> Windows 下如果 `python` 命令不生效，改用 `"command": "cmd", "args": ["/c", "python", "C:\\path\\to\\server.py"]`。

配置完成后，在聊天框选择"Builder with MCP"智能体即可使用。

### OpenAI Codex CLI

Codex 使用 TOML 格式配置（与 Claude/TRAE 的 JSON 不同）。

**配置文件位置**：
- Windows: `C:\Users\<用户名>\.codex\config.toml`
- Linux / macOS: `~/.codex/config.toml`

**配置内容**：

```toml
[mcp_servers.aseprite]
command = "python"
args = ["/path/to/Aseprite_mcp/server.py"]

[mcp_servers.aseprite.env]
ASEPRITE_PATH = "C:\\Program Files\\Aseprite\\aseprite.exe"
```

保存后重启 Codex，在终端内即可调用 Aseprite 工具。

### 验证配置是否成功

配置完成后，在 AI 工具中输入：

> "列出可用的 Aseprite MCP 工具"

如果 AI 能列出 `create_sprite`、`draw_pixel`、`get_canvas_preview` 等工具，说明配置成功。

## 使用

### 直接运行（调试用）

```bash
python server.py
```

### 演示脚本

```bash
python demo.py
```

演示脚本会绘制一个 16x16 的像素艺术笑脸，完整展示创建→绘制→预览→保存的工作流。

## 测试

```bash
# 运行所有单元测试
pytest -v

# 仅运行端到端测试（需要真实 Aseprite）
pytest -v -m e2e

# 运行所有测试（含端到端）
pytest -v -m "e2e or not e2e"
```

## Lua 脚本独立调试

每个 Lua 脚本可独立手动测试：

```powershell
$aseprite = "D:\cxdownload\game_develop\Aseprite-v1.3.17.2-Source\build\bin\aseprite.exe"

# 创建 16x16 画布（注意：--script-param 必须在 --script 之前）
& $aseprite -b --script-param width=16 --script-param height=16 --script-param color_mode=rgb --script-param file=test.ase --script scripts/create_sprite.lua

# 画红色像素
& $aseprite -b --script-param file=test.ase --script-param x=5 --script-param y=5 --script-param color=#FF0000 --script scripts/draw_pixel.lua

# 导出 PNG
& $aseprite -b --script-param file=test.ase --script-param output=test.png --script-param scale=4 --script scripts/export_png.lua
```

## 项目结构

```
Aseprite_mcp/
├── server.py              # MCP 服务器入口
├── src/
│   ├── config.py          # 配置管理
│   ├── session.py         # 会话管理
│   ├── runner.py          # Aseprite 执行器
│   ├── resources.py       # MCP Resources
│   ├── prompts.py         # MCP Prompts
│   └── tools/
│       ├── utils.py       # 工具辅助函数
│       ├── sprite_tools.py    # 精灵管理工具
│       ├── draw_tools.py      # 绘制原语工具
│       └── inspect_tools.py   # 检查与导出工具
├── scripts/               # Aseprite Lua 脚本
│   ├── create_sprite.lua
│   ├── draw_pixel.lua
│   ├── draw_line.lua
│   ├── draw_rect.lua
│   ├── draw_ellipse.lua
│   ├── fill_region.lua
│   ├── clear_region.lua
│   ├── clear_canvas.lua
│   ├── export_png.lua
│   ├── get_pixel_color.lua
│   ├── get_canvas_info.lua
│   ├── open_sprite.lua
│   └── save_sprite.lua
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_session.py
│   ├── test_runner.py
│   ├── test_tools_utils.py
│   ├── test_sprite_tools.py
│   ├── test_draw_tools.py
│   ├── test_inspect_tools.py
│   ├── test_resources.py
│   ├── test_prompts.py
│   └── test_e2e.py
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-07-21-aseprite-mcp-design.md
│       └── plans/
│           └── 2026-07-21-aseprite-mcp.md
└── pyproject.toml
```

## 技术栈

- **Python 3.10+**：主语言
- **FastMCP**：MCP 服务器框架（官方 Python SDK）
- **Aseprite v1.3.17.2**：像素艺术编辑器，通过 CLI + Lua 脚本自动化
- **pytest**：测试框架

## 未来扩展

- 动画支持（多帧、帧持续时间、GIF 导出）
- 图层管理（多图层、可见性、混合模式）
- 调色板管理（自定义调色板、索引颜色模式）
- 图块集（Tileset）支持
- Web UI（HTTP 传输方式）
