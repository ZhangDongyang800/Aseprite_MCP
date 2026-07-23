-- main.lua：Aseprite MCP Bridge 扩展入口
-- 通过 WebSocket 连接到 Python MCP 服务器，实现 AI 对 Aseprite 的实时操作。
--
-- 协议（基于文本行的键值对格式）：
--   请求（Python → Aseprite）: <id>\t<script_name>\t<key1=value1>\t<key2=value2>...
--   响应（Aseprite → Python）: <id>\t<success>\t<stdout_escaped>\t<stderr_escaped>
--
-- 注意：Aseprite Lua 环境没有 loadstring，因此不采用 Lua table literal。
--
-- 用法：
--   1. 在 Aseprite 中安装本扩展（File > Scripts > Open Scripts Folder，或 Extensions 对话框）
--   2. 点击菜单 File > Scripts > MCP Bridge: Toggle Connection
--   3. 确保 Python MCP 服务器已启动且 mode=ws
--   4. 连接成功后，AI 即可直接操作当前 Aseprite 实例

-- ============================================================
-- 配置：默认 WebSocket 服务器地址（可被环境变量覆盖）
-- ============================================================
local BRIDGE_HOST = os.getenv("ASEPRITE_WS_HOST") or "127.0.0.1"
local BRIDGE_PORT = tonumber(os.getenv("ASEPRITE_WS_PORT") or "9001")
local BRIDGE_URL = "ws://" .. BRIDGE_HOST .. ":" .. BRIDGE_PORT

-- ============================================================
-- 辅助函数：转义/反转义（用于响应中的 stdout/stderr）
-- ============================================================

-- 转义 stdout/stderr 以便安全传输（按 \t 分隔的字段不能含原始制表符/换行）
local function escape_text(s)
    s = s or ""
    s = s:gsub("\\", "\\\\")  -- 反斜杠先转义
    s = s:gsub("\t", "\\t")
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    return s
end

-- ============================================================
-- 消息分发：执行 Lua 脚本并捕获 print 输出
-- ============================================================

-- 设置 app.params（兼容 CLI 脚本的 app.params["xxx"] 读取方式）
-- 返回 true 表示成功，false + err 表示失败
local function set_script_params(params)
    params = params or {}
    -- 尝试逐字段写入 app.params
    local ok, err = pcall(function()
        for k, v in pairs(params) do
            app.params[k] = tostring(v)
        end
    end)
    if ok then return true end
    -- 如果 app.params 不可写，尝试整体替换
    ok, err = pcall(function()
        -- 构造一个纯字符串值的 table（模拟 CLI 的 app.params 行为）
        local str_params = {}
        for k, v in pairs(params) do
            str_params[k] = tostring(v)
        end
        app.params = str_params
    end)
    if ok then return true end
    return false, err
end

-- 反转义 Python 端转义的 key/value
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

-- 按 \t 分隔消息，同时处理转义序列（\t、\n、\r、\\、\=）
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
                -- 不认识的转义，保留反斜杠
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

-- 处理单条请求消息，返回响应字符串
local function handle_request(message)
    -- 按 \t 分割：id, script_name, [key1=value1, key2=value2, ...]
    local parts = split_message(message)

    local req_id = parts[1]
    local script_name = parts[2]

    if not req_id or not script_name then
        return req_id and (req_id .. "\tfalse\t\terror: invalid request format") or "error\tfalse\t\tno request id"
    end

    -- 解析参数对 key=value
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

    -- 查找脚本文件
    -- Python 端发送的是脚本文件的绝对路径，因此 script_name 即 script_path
    local script_path = script_name

    -- 检查脚本是否存在
    -- Aseprite 路径分隔符兼容：Windows 路径用反斜杠，但 Lua 字符串里不受影响
    local file = io.open(script_path, "r")
    if not file then
        return req_id .. "\tfalse\t\terror: script not found: " .. script_path
    end
    file:close()

    -- 设置 app.params
    local params_ok, params_err = set_script_params(params)
    if not params_ok then
        return req_id .. "\tfalse\t\terror: cannot set app.params: " .. tostring(params_err)
    end

    -- Live 模式标志：标记当前在 WebSocket 扩展环境中
    -- mcp_common.lua 会读取这个标志来决定是否使用 app.activeSprite
    _G._mcp_live_mode = true

    -- 先加载公共辅助模块（提供 _mcp_get_sprite / _mcp_maybe_save 等函数）
    -- 推导 common 脚本路径：与主脚本在同一目录
    local common_path = script_path:gsub("[^/\\]+$", "mcp_common.lua")
    local common_file = io.open(common_path, "r")
    if common_file then
        common_file:close()
        pcall(dofile, common_path)
    end

    -- 捕获 print 输出
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

    -- 执行脚本
    local success = true
    local err_msg = ""
    local ok2, err2 = pcall(function()
        dofile(script_path)
    end)
    if not ok2 then
        success = false
        err_msg = tostring(err2)
    end

    -- 恢复 print
    _G.print = old_print

    local stdout = table.concat(captured, "\n")
    local stderr = success and "" or err_msg

    -- 构造响应
    return req_id .. "\t" .. tostring(success) .. "\t" .. escape_text(stdout) .. "\t" .. escape_text(stderr)
end

-- ============================================================
-- WebSocket 连接管理
-- ============================================================

-- 检查是否已连接
if _G._mcp_ws then
    -- 已连接，关闭连接
    local ws = _G._mcp_ws
    _G._mcp_ws = nil
    pcall(function() ws:close() end)
    app.alert("MCP Bridge: Disconnected from " .. BRIDGE_URL)
    return
end

-- 创建 WebSocket client
local ws = WebSocket{
    url = BRIDGE_URL,
    deflate = false,
    minreconnectwait = 0.5,
    maxreconnectwait = 3.0,
    onreceive = function(mt, data)
        if mt == WebSocketMessageType.OPEN then
            -- 连接建立
            app.alert("MCP Bridge: Connected to " .. BRIDGE_URL)
        elseif mt == WebSocketMessageType.TEXT then
            -- 收到请求，处理并回传响应
            local response = handle_request(data)
            if response and _G._mcp_ws then
                _G._mcp_ws:sendText(response)
            end
        elseif mt == WebSocketMessageType.CLOSE then
            -- 连接关闭
            _G._mcp_ws = nil
            app.alert("MCP Bridge: Connection closed")
        end
    end
}

-- 启动连接
ws:connect()
_G._mcp_ws = ws

-- 提示用户
app.alert("MCP Bridge: Connecting to " .. BRIDGE_URL .. " ...\n"
    .. "Click again to disconnect.\n"
    .. "Make sure the MCP server is running with ASEPRITE_MCP_MODE=ws")
