-- duplicate_frame.lua：复制指定帧
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local frame_idx = tonumber(app.params["frame"] or "1")
local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite

if frame_idx < 1 or frame_idx > #sprite.frames then
    print("ERROR: frame out of range: " .. frame_idx)
    return
end
app.activeFrame = sprite.frames[frame_idx]
app.command.DuplicateFrame()
_mcp_maybe_save(sprite, file)
print("OK: duplicated frame " .. frame_idx)