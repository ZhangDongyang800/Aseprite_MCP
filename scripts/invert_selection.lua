-- invert_selection.lua：反选
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite
app.command.InvertMask()
local sel_path = app.params["sel_path"]
if sel_path and sel_path ~= "" then _G._mcp_save_selection(sprite, sel_path) end
_mcp_maybe_save(sprite, file)
print("OK: inverted selection")