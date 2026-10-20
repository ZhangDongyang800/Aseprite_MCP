"""Aseprite MCP v2 kernel package."""

# Settled by the capability probe in Task 0.2 (measured against fastmcp 4.0.5, see
# tests/v2/test_fastmcp_capabilities.py):
# a tool may return fastmcp.tools.ToolResult(
#     content=[Image(...)], structured_content={...}
# ), and a single client call_tool receives both the ImageContent and the structured
# dict. That is why the v2 inspect tool uses the "tool_result" combined-response mode.
IMAGE_STRUCTURED_MODE = "tool_result"
