"""server.py 工具注册测试（v2 三工具面）。

server 只注册 v2 的 apply_operations / inspect / run_lua；v1 的
register_*_tools 已随 src/tools/ 一起删除，这个集合就是它们的反面。
"""

import asyncio

EXPECTED_TOOLS = {"apply_operations", "inspect", "run_lua"}


def test_v2_tools_registered():
    """create_server() 只注册 v2 的三个工具。"""
    from server import create_server

    mcp = create_server()
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS
