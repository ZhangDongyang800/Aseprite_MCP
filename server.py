"""Aseprite MCP 服务器入口。

创建 FastMCP 实例，注册所有工具、资源和提示，启动服务器。
"""

import sys
import threading
from pathlib import Path

# 确保能导入 src 包
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

from src.config import Config
from src.session import SessionManager
from src.runner import AsepriteRunner
from src.tools.sprite_tools import register_sprite_tools
from src.tools.draw_tools import register_draw_tools
from src.tools.advanced_draw_tools import register_advanced_draw_tools
from src.tools.inspect_tools import register_inspect_tools
from src.tools.animation_tools import register_animation_tools
from src.tools.layer_tools import register_layer_tools
from src.tools.palette_tools import register_palette_tools
from src.tools.tag_tools import register_tag_tools
from src.tools.transform_tools import register_transform_tools
# Task 13: 新增工具模块导入
from src.tools.tileset_tools import register_tileset_tools
from src.tools.quality_tools import register_quality_tools
from src.resources import register_resources
from src.prompts import register_prompts


def create_server() -> FastMCP:
    """创建并配置 FastMCP 服务器实例。

    Returns:
        配置好的 FastMCP 实例
    """
    # 加载配置
    config = Config()

    # 检查 Aseprite 是否存在
    runner = AsepriteRunner(config)
    if not runner.check_aseprite_exists():
        print(
            f"WARNING: Aseprite not found at {config.aseprite_path}\n"
            f"Set ASEPRITE_PATH environment variable to the correct path.",
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
    # Task 13: 注册新增工具模块
    register_tileset_tools(mcp, session_manager, runner)
    register_quality_tools(mcp, session_manager, runner)

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
