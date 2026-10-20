"""Tests for the tool registration in server.py (the v2 three-tool surface).

The server registers only the v2 apply_operations / inspect / run_lua; the v1
register_*_tools were deleted along with src/tools/, so this set is what
replaced them.
"""

import asyncio

EXPECTED_TOOLS = {"apply_operations", "inspect", "run_lua"}


def test_v2_tools_registered():
    """create_server() registers exactly the three v2 tools."""
    from server import create_server

    mcp = create_server()
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS
