"""Aseprite MCP server entry point.

Creates the FastMCP instance, registers the three-tool v2 surface
(apply_operations / inspect / run_lua) plus resources and prompts, and starts the server.

Two execution modes, switched with the ASEPRITE_MCP_MODE environment variable:
- cli (default): runs the Aseprite CLI through subprocess; no UI, no persistent state
- ws: connects over WebSocket to a running Aseprite instance; visible UI, persistent state
"""

import sys
import threading
from pathlib import Path

# Make the src package importable
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

from src.config import Config
from src.session import SessionManager
from src.runner import AsepriteRunner, WebSocketRunner
from src.v2.tools import register_v2_tools
from src.resources import register_resources
from src.prompts import register_prompts


def create_server() -> FastMCP:
    """Create and configure the FastMCP server instance.

    Returns:
        the configured FastMCP instance
    """
    # Load configuration
    config = Config()

    # Build the runner for the selected mode
    if config.mode == "ws":
        # WebSocket mode: start the WebSocket server and wait for the Aseprite extension
        from src.bridge import WebSocketBridge

        bridge = WebSocketBridge(host=config.ws_host, port=config.ws_port)
        if not bridge.start(timeout=5.0):
            print(
                f"ERROR: Failed to start WebSocket server on {config.ws_host}:{config.ws_port}",
                file=sys.stderr,
            )
            print("Falling back to CLI mode.", file=sys.stderr)
            runner = AsepriteRunner(config)
            config.mode = "cli"  # keep this in step with the runner (spec P0-8)
        else:
            runner = WebSocketRunner(bridge=bridge, config=config)
            print(
                f"[MCP] WebSocket mode enabled. Server: ws://{config.ws_host}:{config.ws_port}\n"
                f"[MCP] Please install the Aseprite extension (in extension/ folder) and click\n"
                f"[MCP] 'File > Scripts > MCP Bridge: Toggle Connection' in Aseprite to connect.",
                file=sys.stderr,
            )
    else:
        # CLI mode (default)
        runner = AsepriteRunner(config)

    # Check Aseprite is usable (path in CLI mode, connection in ws mode)
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

    # Build the core components
    session_manager = SessionManager(config)
    # Session directories left by a previous process are invisible to the in-memory
    # registry, so sweep the filesystem by age once at startup
    session_manager.cleanup_expired()

    # Create the FastMCP server
    mcp = FastMCP("AsepriteMCP")

    # Register tools (the three-tool v2 surface; the v1 register_*_tools went with src/tools/)
    register_v2_tools(mcp, session_manager, runner, config)

    # Register resources
    register_resources(mcp, session_manager)

    # Register prompts
    register_prompts(mcp)

    # Start the background session-cleanup thread
    cleanup_interval = 300  # sweep every 5 minutes
    cleanup_thread = threading.Thread(
        target=_cleanup_loop,
        args=(session_manager, cleanup_interval),
        daemon=True,
    )
    cleanup_thread.start()

    return mcp


def _cleanup_loop(session_manager: SessionManager, interval: int):
    """Session-cleanup loop (background daemon thread).

    Args:
        session_manager: the session manager
        interval: seconds between sweeps
    """
    import time

    while True:
        time.sleep(interval)
        try:
            session_manager.cleanup_expired()
        except Exception as e:
            print(f"Session cleanup error: {e}", file=sys.stderr)


# Module-level instance for the FastMCP CLI
mcp = create_server()


if __name__ == "__main__":
    mcp.run()
