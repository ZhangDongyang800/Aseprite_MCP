-- apply_blur.lua：Box blur 滤镜
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local radius = tonumber(app.params["radius"] or "1")
local strength = tonumber(app.params["strength"] or "1")
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")

local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite
local image, err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then print("ERROR: " .. err) return end

_G._mcp_blur(image, radius, strength)
_mcp_maybe_save(sprite, file)
print("OK: applied blur radius=" .. radius)