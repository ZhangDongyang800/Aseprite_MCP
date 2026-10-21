"""The two FastMCP capabilities this server actually depends on.

The rest of FastMCP's API surface is the library's contract, not ours; if it
changes, import errors already fail every other test.
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


@pytest.mark.asyncio
async def test_call_tool_returns_image_and_structured_content_together():
    """One inspect call must carry both the preview image and the metrics dict."""
    mcp = _probe_server()

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "probe")
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False

        result = await client.call_tool("probe", {"x": 7})

    image_blocks = [c for c in result.content if getattr(c, "type", None) == "image"]
    assert image_blocks and image_blocks[0].mime_type == "image/png"
    assert result.structured_content == {"x": 7, "ok": True}


def test_image_structured_mode_constant_matches_the_probe():
    assert IMAGE_STRUCTURED_MODE == "tool_result"
