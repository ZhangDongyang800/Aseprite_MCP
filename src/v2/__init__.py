"""Aseprite MCP v2 内核包。"""

# 由 Task 0.2 的能力探测决定(fastmcp 4.0.5 实测,见
# tests/v2/test_fastmcp_capabilities.py):
# 工具可以返回 fastmcp.tools.ToolResult(
#     content=[Image(...)], structured_content={...}
# ),客户端单次 call_tool 同时收到 ImageContent 与结构化 dict。
# 因此 v2 inspect 工具采用 "tool_result" 同返模式。
IMAGE_STRUCTURED_MODE = "tool_result"
