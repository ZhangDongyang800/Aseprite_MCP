-- main.lua：Aseprite MCP Bridge 扩展入口
-- 通过 WebSocket 连接到 Python MCP 服务器，实现 AI 对 Aseprite 的实时操作。
--
-- 协议（基于文本行的 JSON-RPC 风格）：
--   请求（Python → Aseprite）: <id>\t<script_name>\t<lua_table_literal>
--   响应（Aseprite → Python）: <id>\t<success>\t<stdout_escaped>\t<stderr_escaped>
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

-- 处理单条请求消息，返回响应字符串
local function handle_request(message)
    -- 按 \t 分割：id, script_name, lua_table_literal
    local parts = {}
    local start = 1
    while true do
        local sep = message:find("\t", start, true)
        if not sep then
            parts[#parts + 1] = message:sub(start)
            break
        end
        parts[#parts + 1] = message:sub(start, sep - 1)
        start = sep + 1
        if #parts >= 2 then
            -- 剩余部分作为 lua_table_literal（可能含空格，不分隔）
            parts[#parts + 1] = message:sub(start)
            break
        end
    end

    local req_id = parts[1]
    local script_name = parts[2]
    local lua_literal = parts[3] or "{}"

    if not req_id or not script_name then
        return req_id and (req_id .. "\tfalse\t\terror: invalid request format") or "error\tfalse\t\tno request id"
    end

    -- 解析 Lua table literal
    local params
    local ok, result = pcall(loadstring("return " .. lua_literal))
    if ok and type(result) == "table" then
        params = result
    else
        return req_id .. "\tfalse\t\terror: failed to parse params: " .. tostring(result)
    end

    -- 查找脚本文件
    -- 优先从 app.params 中获取 scripts_dir（由 Python 端在连接时设置）
    -- 否则尝试常见路径
    local scripts_dir = _G._mcp_scripts_dir
    if not scripts_dir then
        -- 尝试从环境变量获取
        scripts_dir = os.getenv("ASEPRITE_SCRIPTS_DIR") or ""
    end

    local script_path
    if scripts_dir and scripts_dir ~= "" then
        script_path = scripts_dir .. "/" .. script_name
    else
        script_path = script_name
    end

    -- 检查脚本是否存在
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
