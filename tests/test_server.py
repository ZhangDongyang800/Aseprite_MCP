"""server.py 工具模块注册测试。

验证 create_server() 会导入并注册所有工具模块（含 Task 13 新增的
tileset_tools 与 quality_tools）。
"""

from unittest.mock import patch


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
