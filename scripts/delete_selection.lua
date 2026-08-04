-- delete_selection.lua：清除选区内容（设为透明）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite
local sel = sprite.selection
if sel.isEmpty then print("OK: no selection, nothing deleted") return end
local image, err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then print("ERROR: " .. err) return end
local transparent = Color{r=0,g=0,b=0,a=0}
local b = sel.bounds
local deleted = 0
for py = b.y, b.y+b.height-1 do
    for px = b.x, b.x+b.width-1 do
        if sel:contains(Point(px, py)) then
            image:drawPixel(px, py, transparent)
            deleted = deleted + 1
        end
    end
end
_mcp_maybe_save(sprite, file)
print('{"deleted":' .. deleted .. '}')