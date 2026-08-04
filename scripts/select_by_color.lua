-- select_by_color.lua：按颜色选区（魔棒）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local color_hex = app.params["color"]
local tolerance = tonumber(app.params["tolerance"] or "0")
if not color_hex then print("ERROR: color is required") return end
local r, g, b = _mcp_hex_to_rgb(color_hex)
local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite
app.fgColor = Color{r=r, g=g, b=b}
-- 使用 SelectionMode.REPLACE (默认)
app.command.MaskByColor{ui=false, color=app.fgColor, tolerance=tolerance}
local sel_path = app.params["sel_path"]
if sel_path and sel_path ~= "" then _G._mcp_save_selection(sprite, sel_path) end
_mcp_maybe_save(sprite, file)
print("OK: selected by color " .. color_hex)