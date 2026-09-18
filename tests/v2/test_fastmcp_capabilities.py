"""FastMCP 4 能力探测:图片 + 结构化同返与工具注解。

2026-09-18 在 fastmcp 4.0.5 上实测(内存在途 + 真实 stdio 子进程):

- ``@mcp.tool(annotations={...})`` 受支持,注解经 ``list_tools()`` 暴露为
  ``ToolAnnotations(read_only_hint=..., open_world_hint=...)``。
- ``from fastmcp.tools import ToolResult``(定义于
  ``fastmcp.tools.base.ToolResult``)可用 ``content + structured_content``
  同时携带图片与结构化数据。
- 工具返回 ``ToolResult(content=[Image(data=..., format="png")],
  structured_content={...})`` 时,客户端单次 ``call_tool`` 即同时收到
  ``ImageContent`` 与结构化 dict(``result.content`` / ``result.structured_content``)。

因此 ``src.v2.IMAGE_STRUCTURED_MODE == "tool_result"``。若下列 API 消失,
这些测试应失败,提示需要重新探测并回退为 ``"image_only"``。
"""

import base64

import pytest
from fastmcp import Client, FastMCP
from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image

from src.v2 import IMAGE_STRUCTURED_MODE

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _probe_server() -> FastMCP:
    mcp = FastMCP("probe")

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def probe(x: int) -> ToolResult:
        return ToolResult(
            content=[Image(data=PNG_1X1, format="png"), "hello"],
            structured_content={"x": x, "ok": True},
        )

    return mcp


def test_fastmcp_version_is_4():
    import fastmcp

    assert fastmcp.__version__.startswith("4.")


def test_lazy_exports_expose_fastmcp_and_client():
    """FastMCP 4 顶层通过惰性 __getattr__ 导出;断言公开 API 仍在。"""
    import fastmcp

    assert "FastMCP" in fastmcp.__all__
    assert "Client" in fastmcp.__all__
    assert fastmcp.FastMCP is FastMCP
    assert fastmcp.Client is Client


def test_tool_decorator_accepts_annotations():
    mcp = FastMCP("probe")

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def probe(x: int) -> dict:
        return {"x": x}

    assert callable(probe)


def test_tool_result_import_path_and_fields():
    result = ToolResult(
        content=[Image(data=PNG_1X1, format="png")],
        structured_content={"x": 1},
    )
    assert result.structured_content == {"x": 1}
    assert len(result.content) == 1
    assert result.content[0].type == "image"


def test_image_import_path_and_conversion():
    image = Image(data=PNG_1X1, format="png")
    content = image.to_image_content()
    assert content.type == "image"
    assert content.mime_type == "image/png"


@pytest.mark.asyncio
async def test_call_tool_returns_image_and_structured_content_together():
    """核心能力:单次调用同时拿到图片与结构化 JSON。"""
    mcp = _probe_server()

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "probe")
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False

        result = await client.call_tool("probe", {"x": 7})

    image_blocks = [c for c in result.content if getattr(c, "type", None) == "image"]
    assert image_blocks, "图片内容块缺失"
    assert image_blocks[0].mime_type == "image/png"
    assert result.structured_content == {"x": 7, "ok": True}
    assert result.data == {"x": 7, "ok": True}


def test_image_structured_mode_constant_matches_probe():
    assert IMAGE_STRUCTURED_MODE == "tool_result"
