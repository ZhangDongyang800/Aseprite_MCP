"""server.py 工具注册测试（v2 三工具面）。

Task 1.9 起 server 只注册 v2 的 apply_operations / run_lua / inspect，
旧 register_*_tools 不再调用（模块与直接测模块的用例暂留，阶段 3 清理）。
"""

import asyncio
from unittest.mock import patch

import pytest

EXPECTED_TOOLS = {"apply_operations", "inspect", "run_lua"}


def test_v2_tools_registered():
    """create_server() 只注册 v2 的三个工具。"""
    from server import create_server

    mcp = create_server()
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS


@pytest.mark.skip(reason="retired in v2")
def test_create_server_registers_tileset_and_quality_tools():
    """create_server 应导入并注册 tileset_tools 与 quality_tools 模块。"""
    import server

    # 验证 import 已就位（Task 13 Step 1）
    assert hasattr(server, "register_tileset_tools"), (
        "server.py 未导入 register_tileset_tools"
    )
    assert hasattr(server, "register_quality_tools"), (
        "server.py 未导入 register_quality_tools"
    )

    # 验证 create_server 中确实调用了这两个注册函数（Task 13 Step 2）
    with patch.object(server, "register_tileset_tools") as mock_tileset, \
            patch.object(server, "register_quality_tools") as mock_quality:
        server.create_server()
        mock_tileset.assert_called_once()
        mock_quality.assert_called_once()
