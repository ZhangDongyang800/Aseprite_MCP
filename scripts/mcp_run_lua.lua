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

-- code arriving as a key=value param string cannot carry a snippet, so v2 bypasses it with a file:
-- Python writes <work>/_run_lua.lua and puts that path in the code_path param
if app.params["code_path"] and app.params["code_path"] ~= "" then
    dofile(app.params["code_path"])
else
    error("code_path is required")
end
_G._mcp_maybe_save(sprite, file)
