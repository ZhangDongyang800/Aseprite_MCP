"""Aseprite MCP 服务器入口。

创建 FastMCP 实例，注册所有工具、资源和提示，启动服务器。

支持两种执行模式（通过 ASEPRITE_MCP_MODE 环境变量切换）：
- cli（默认）：通过 subprocess 调用 Aseprite CLI，无 UI、无状态持久
- ws：通过 WebSocket 连接运行中的 Aseprite 实例，UI 可见、状态持久
"""

import sys
import threading
from pathlib import Path

# 确保能导入 src 包
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

from src.config import Config
from src.session import SessionManager
from src.runner import AsepriteRunner, WebSocketRunner
from src.tools.sprite_tools import register_sprite_tools
from src.tools.draw_tools import register_draw_tools
from src.tools.advanced_draw_tools import register_advanced_draw_tools
from src.tools.inspect_tools import register_inspect_tools
from src.tools.animation_tools import register_animation_tools
from src.tools.layer_tools import register_layer_tools
from src.tools.palette_tools import register_palette_tools
from src.tools.tag_tools import register_tag_tools
from src.tools.transform_tools import register_transform_tools
from src.tools.tileset_tools import register_tileset_tools
from src.tools.quality_tools import register_quality_tools
from src.tools.selection_tools import register_selection_tools
from src.tools.color_adjustment_tools import register_color_adjustment_tools
from src.tools.filter_tools import register_filter_tools
from src.tools.batch_tools import register_batch_tools
from src.tools.import_tools import register_import_tools
from src.resources import register_resources
from src.prompts import register_prompts


def create_server() -> FastMCP:
    """创建并配置 FastMCP 服务器实例。

    Returns:
        配置好的 FastMCP 实例
    """
    # 加载配置
    config = Config()

    # 根据模式创建 runner
    if config.mode == "ws":
        # WebSocket 模式：启动 WebSocket server，等待 Aseprite 扩展连接
        from src.bridge import WebSocketBridge

        bridge = WebSocketBridge(host=config.ws_host, port=config.ws_port)
        if not bridge.start(timeout=5.0):
            print(
                f"ERROR: Failed to start WebSocket server on {config.ws_host}:{config.ws_port}",
                file=sys.stderr,
            )
            print("Falling back to CLI mode.", file=sys.stderr)
            runner = AsepriteRunner(config)
        else:
            runner = WebSocketRunner(bridge=bridge, config=config)
            print(
                f"[MCP] WebSocket mode enabled. Server: ws://{config.ws_host}:{config.ws_port}\n"
                f"[MCP] Please install the Aseprite extension (in extension/ folder) and click\n"
                f"[MCP] 'File > Scripts > MCP Bridge: Toggle Connection' in Aseprite to connect.",
                file=sys.stderr,
            )
    else:
        # CLI 模式（默认）
        runner = AsepriteRunner(config)

    # 检查 Aseprite 是否可用（CLI 模式检查路径，WS 模式检查连接）
    if not runner.check_aseprite_exists():
        if config.mode == "cli":
            print(
                f"WARNING: Aseprite not found at {config.aseprite_path}\n"
                f"Set ASEPRITE_PATH environment variable to the correct path.",
                file=sys.stderr,
            )
        else:
            print(
                "WARNING: Aseprite extension is not connected yet.\n"
                "Please install the extension and click 'Toggle Connection' in Aseprite.",
                file=sys.stderr,
            )

    # 创建核心组件
    session_manager = SessionManager(config)

    # 创建 FastMCP 服务器
    mcp = FastMCP("AsepriteMCP")

    # 注册工具
    register_sprite_tools(mcp, session_manager, runner)
    register_draw_tools(mcp, session_manager, runner)
    register_advanced_draw_tools(mcp, session_manager, runner)
    register_inspect_tools(mcp, session_manager, runner)
    register_animation_tools(mcp, session_manager, runner)
    register_layer_tools(mcp, session_manager, runner)
    register_palette_tools(mcp, session_manager, runner)
    register_tag_tools(mcp, session_manager, runner)
    register_transform_tools(mcp, session_manager, runner)
    register_tileset_tools(mcp, session_manager, runner)
    register_quality_tools(mcp, session_manager, runner)
    # New: selection, color adjustment, filter, batch tools
    register_selection_tools(mcp, session_manager, runner)
    register_color_adjustment_tools(mcp, session_manager, runner)
    register_filter_tools(mcp, session_manager, runner)
    register_batch_tools(mcp, session_manager, runner)
    register_import_tools(mcp, session_manager, runner)

    # 注册资源
    register_resources(mcp, session_manager)

    # 注册提示
    register_prompts(mcp)

    # 启动会话清理后台线程
    cleanup_interval = 300  # 每 5 分钟清理一次
    cleanup_thread = threading.Thread(
        target=_cleanup_loop,
        args=(session_manager, cleanup_interval),
        daemon=True,
    )
    cleanup_thread.start()

    return mcp


def _cleanup_loop(session_manager: SessionManager, interval: int):
    """会话清理循环（后台守护线程）。

    Args:
        session_manager: 会话管理器
        interval: 清理间隔（秒）
    """
    import time

    while True:
        time.sleep(interval)
        try:
            session_manager.cleanup_expired()
        except Exception as e:
            print(f"Session cleanup error: {e}", file=sys.stderr)


# 模块级别实例，供 FastMCP CLI 使用
mcp = create_server()


if __name__ == "__main__":
    mcp.run()
