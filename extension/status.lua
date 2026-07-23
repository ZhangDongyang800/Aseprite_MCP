-- status.lua：显示 MCP Bridge 连接状态

local BRIDGE_HOST = os.getenv("ASEPRITE_WS_HOST") or "127.0.0.1"
local BRIDGE_PORT = tonumber(os.getenv("ASEPRITE_WS_PORT") or "9001")

if _G._mcp_ws then
    app.alert("MCP Bridge: CONNECTED\n"
        .. "Server: ws://" .. BRIDGE_HOST .. ":" .. BRIDGE_PORT .. "\n"
        .. "Scripts dir: " .. tostring(_G._mcp_scripts_dir or "(not set, using script name as path)"))
else
    app.alert("MCP Bridge: DISCONNECTED\n"
        .. "Expected server: ws://" .. BRIDGE_HOST .. ":" .. BRIDGE_PORT .. "\n"
        .. "Click 'MCP Bridge: Toggle Connection' to connect.")
end
