-- deselect.lua：取消选区
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite
app.command.DeselectMask()
local sel_path = app.params["sel_path"]
if sel_path and sel_path ~= "" then
    local f = io.open(sel_path, "w")
    if f then f:write("0 0\n"); f:close() end
end
_mcp_maybe_save(sprite, file)
print("OK: deselected")