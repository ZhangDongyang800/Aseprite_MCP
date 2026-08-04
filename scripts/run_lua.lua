-- run_lua.lua：在 Aseprite 中执行任意 Lua 代码（逃逸舱）
-- 参数: file, code (Lua 代码字符串)
-- 代码可访问 sprite, app, _G._mcp_* 全局函数
-- 所有 print 输出被捕获并返回

if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local code = app.params["code"]

if not code or code == "" then
    print('{"error":"code parameter is required"}')
    return
end

local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print('{"error":"no active sprite"}')
    return
end

app.activeSprite = sprite

-- 捕获 print 输出
local captured = {}
local old_print = _G.print
_G.print = function(...)
    local args = {...}
    local strs = {}
    for i = 1, #args do
        strs[i] = tostring(args[i])
    end
    captured[#captured + 1] = table.concat(strs, "\t")
end

-- 执行用户代码
local ok, err = pcall(function()
    local fn, load_err = load(code)
    if not fn then
        error("syntax error: " .. tostring(load_err))
    end
    fn()
end)

_G.print = old_print
_mcp_maybe_save(sprite, file)

local stdout = table.concat(captured, "\n")
if ok then
    print(stdout)
else
    print('{"error":"' .. tostring(err):gsub('"', '\\"'):gsub("\n", "\\n") .. '","stdout":"' .. stdout:gsub('"', '\\"'):gsub("\n", "\\n") .. '"}')
end