-- main.lua: entry point of the Aseprite MCP Bridge extension
-- Talks to the Python MCP server over WebSocket so an AI can drive Aseprite live.
--
-- Protocol (text lines carrying tab-separated key=value fields):
--   Request (Python → Aseprite): <id>\t<script_name>\t<key1=value1>\t<key2=value2>...
--   Response (Aseprite → Python): <id>\t<success>\t<stdout_escaped>\t<stderr_escaped>
--
-- Note: the Aseprite Lua environment has no loadstring, so no Lua table literal here.
--
-- Usage:
--   1. Install the extension in Aseprite (File > Scripts > Open Scripts Folder, or Extensions)
--   2. Click File > Scripts > MCP Bridge: Toggle Connection
--   3. Make sure the Python MCP server is running with mode=ws
--   4. Once connected, the AI can drive this Aseprite instance directly

-- ============================================================
-- Config: default WebSocket server address (env vars can override it)
-- ============================================================
local BRIDGE_HOST = os.getenv("ASEPRITE_WS_HOST") or "127.0.0.1"
local BRIDGE_PORT = tonumber(os.getenv("ASEPRITE_WS_PORT") or "9001")
local BRIDGE_URL = "ws://" .. BRIDGE_HOST .. ":" .. BRIDGE_PORT

-- ============================================================
-- Helpers: escape/unescape (for stdout/stderr in the response)
-- ============================================================

-- Escape stdout/stderr for transport (tab-separated fields cannot hold a raw tab/newline)
local function escape_text(s)
    s = s or ""
    s = s:gsub("\\", "\\\\")  -- escape backslashes first
    s = s:gsub("\t", "\\t")
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    return s
end

-- ============================================================
-- Message dispatch: run a Lua script and capture its print output
-- ============================================================

-- Set app.params (matching how CLI scripts read app.params["xxx"])
-- Returns true on success, false + err on failure
local function set_script_params(params)
    params = params or {}
    -- Fresh table every request: app.params survives, so leftovers leak into the next call
    local ok, err = pcall(function()
        local str_params = {}
        for k, v in pairs(params) do
            str_params[k] = tostring(v)
        end
        app.params = str_params
    end)
    if ok then return true end
    -- Fall back to writing field by field when app.params cannot be replaced wholesale
    ok, err = pcall(function()
        for k, v in pairs(params) do
            app.params[k] = tostring(v)
        end
    end)
    if ok then return true end
    return false, err
end

-- Unescape the key/value strings escaped by the Python side
local function unescape_value(s)
    s = s or ""
    local result = {}
    local i = 1
    while i <= #s do
        local c = s:sub(i, i)
        if c == "\\" and i < #s then
            local next_c = s:sub(i + 1, i + 1)
            if next_c == "t" then
                table.insert(result, "\t")
            elseif next_c == "n" then
                table.insert(result, "\n")
            elseif next_c == "r" then
                table.insert(result, "\r")
            elseif next_c == "\\" then
                table.insert(result, "\\")
            elseif next_c == "=" then
                table.insert(result, "=")
            else
                table.insert(result, c)
                table.insert(result, next_c)
            end
            i = i + 2
        else
            table.insert(result, c)
            i = i + 1
        end
    end
    return table.concat(result)
end

-- Split on \t while resolving escape sequences (\t, \n, \r, \\, \=)
local function split_message(message)
    local parts = {}
    local current = {}
    local i = 1
    while i <= #message do
        local c = message:sub(i, i)
        if c == "\\" and i < #message then
            local next_c = message:sub(i + 1, i + 1)
            if next_c == "t" then
                table.insert(current, "\t")
                i = i + 2
            elseif next_c == "n" then
                table.insert(current, "\n")
                i = i + 2
            elseif next_c == "r" then
                table.insert(current, "\r")
                i = i + 2
            elseif next_c == "=" then
                table.insert(current, "=")
                i = i + 2
            elseif next_c == "\\" then
                table.insert(current, "\\")
                i = i + 2
            else
                -- Unknown escape: keep the backslash
                table.insert(current, c)
                i = i + 1
            end
        elseif c == "\t" then
            table.insert(parts, table.concat(current))
            current = {}
            i = i + 1
        else
            table.insert(current, c)
            i = i + 1
        end
    end
    table.insert(parts, table.concat(current))
    return parts
end

-- Handle one request message and return the response string
local function handle_request(message)
    -- Split on \t: id, script_name, [key1=value1, key2=value2, ...]
    local parts = split_message(message)

    local req_id = parts[1]
    local script_name = parts[2]

    if not req_id or not script_name then
        -- The protocol fixes 4 fields; drop one and Python cannot parse it and hangs to timeout
        return req_id and (req_id .. "\tfalse\t\terror: invalid request format\t")
            or "error\tfalse\t\tno request id\t"
    end

    -- Parse the key=value pairs
    local params = {}
    for i = 3, #parts do
        local part = parts[i]
        local eq_pos = part:find("=", 1, true)
        if eq_pos then
            local key = unescape_value(part:sub(1, eq_pos - 1))
            local value = unescape_value(part:sub(eq_pos + 1))
            params[key] = value
        end
    end

    -- Find the script file
    -- Python sends the script's absolute path, so script_name is script_path
    local script_path = script_name

    -- Check that the script exists
    -- Path separators: Windows paths use backslashes, which is harmless inside a Lua string
    local file = io.open(script_path, "r")
    if not file then
        return req_id .. "\tfalse\t\terror: script not found: " .. script_path .. "\t"
    end
    file:close()

    -- Set app.params
    local params_ok, params_err = set_script_params(params)
    if not params_ok then
        return req_id .. "\tfalse\t\terror: cannot set app.params: " .. tostring(params_err) .. "\t"
    end

    -- Live-mode flag: marks the current environment as the WebSocket extension
    -- mcp_common.lua reads this flag to decide whether to use app.activeSprite
    _G._mcp_live_mode = true

    -- Load the shared helpers first (they provide _mcp_get_sprite / _mcp_maybe_save, ...)
    -- Derive the common script path: same directory as the main script
    local common_path = script_path:gsub("[^/\\]+$", "mcp_common.lua")
    local common_file = io.open(common_path, "r")
    if common_file then
        common_file:close()
        pcall(dofile, common_path)
    end

    -- Capture print output
    local captured = {}
    local old_print = _G.print
    _G.print = function(...)
        local args = { ... }
        local strs = {}
        for i = 1, #args do
            strs[i] = tostring(args[i])
        end
        captured[#captured + 1] = table.concat(strs, "\t")
    end

    -- Run the script
    local success = true
    local err_msg = ""
    local ok2, err2 = pcall(function()
        dofile(script_path)
    end)
    if not ok2 then
        success = false
        err_msg = tostring(err2)
    end

    -- Restore print
    _G.print = old_print

    local stdout = table.concat(captured, "\n")
    local stderr = success and "" or err_msg

    -- Build the response
    return req_id .. "\t" .. tostring(success) .. "\t" .. escape_text(stdout) .. "\t" .. escape_text(stderr)
end

-- ============================================================
-- WebSocket connection management
-- ============================================================

-- Check whether we are already connected
if _G._mcp_ws then
    -- Already connected: close the connection
    local ws = _G._mcp_ws
    _G._mcp_ws = nil
    pcall(function() ws:close() end)
    app.alert("MCP Bridge: Disconnected from " .. BRIDGE_URL)
    return
end

-- Create the WebSocket client
local ws = WebSocket{
    url = BRIDGE_URL,
    deflate = false,
    minreconnectwait = 0.5,
    maxreconnectwait = 3.0,
    onreceive = function(mt, data)
        if mt == WebSocketMessageType.OPEN then
            -- Connection established
            app.alert("MCP Bridge: Connected to " .. BRIDGE_URL)
        elseif mt == WebSocketMessageType.TEXT then
            -- Request received: handle it and send the response back
            local response = handle_request(data)
            if response and _G._mcp_ws then
                _G._mcp_ws:sendText(response)
            end
        elseif mt == WebSocketMessageType.CLOSE then
            -- Connection closed
            _G._mcp_ws = nil
            app.alert("MCP Bridge: Connection closed")
        end
    end
}

-- Start the connection
ws:connect()
_G._mcp_ws = ws

-- Prompt the user
app.alert("MCP Bridge: Connecting to " .. BRIDGE_URL .. " ...\n"
    .. "Click again to disconnect.\n"
    .. "Make sure the MCP server is running with ASEPRITE_MCP_MODE=ws")
