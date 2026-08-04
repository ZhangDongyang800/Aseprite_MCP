-- draw_gradient.lua：渐变填充
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local x = tonumber(app.params["x"] or "0")
local y = tonumber(app.params["y"] or "0")
local w = tonumber(app.params["width"] or "16")
local h = tonumber(app.params["height"] or "16")
local from_hex = app.params["from_color"]
local to_hex = app.params["to_color"]
local mode = app.params["mode"] or "linear"
local direction = app.params["direction"] or "horizontal"
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")

if not from_hex or not to_hex then
    print("ERROR: from_color and to_color are required")
    return
end

local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite
local image, err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then print("ERROR: " .. err) return end

local fr, fg, fb = _mcp_hex_to_rgb(from_hex)
local tr, tg, tb = _mcp_hex_to_rgb(to_hex)
local from_c = Color{r=fr, g=fg, b=fb, a=255}
local to_c = Color{r=tr, g=tg, b=tb, a=255}

_G._mcp_gradient(image, x, y, w, h, from_c, to_c, mode, direction)
_mcp_maybe_save(sprite, file)
print("OK: drew " .. mode .. " gradient")