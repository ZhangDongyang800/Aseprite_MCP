if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

local file = app.params["file"]
local code = app.params["code"] or ""
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    error("no sprite. Call create_sprite first.")
end

-- code 以 params 传入的是 key=value 字符串；v2 改用文件旁路：
-- Python 写 <work>/_run_lua.lua 并把路径放入 code 参数
if app.params["code_path"] and app.params["code_path"] ~= "" then
    dofile(app.params["code_path"])
else
    error("code_path is required")
end
_G._mcp_maybe_save(sprite, file)
