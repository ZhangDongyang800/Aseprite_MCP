-- adjust_colors.lua：统一颜色调整（亮度/对比度/色相/饱和度/明度）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite

local brightness = tonumber(app.params["brightness"] or "0")
local contrast = tonumber(app.params["contrast"] or "0")
local hue = tonumber(app.params["hue"] or "0")
local saturation = tonumber(app.params["saturation"] or "0")
local lightness = tonumber(app.params["lightness"] or "0")

if brightness ~= 0 or contrast ~= 0 then
    app.command.BrightnessContrast{ui=false, brightness=brightness, contrast=contrast}
end
if hue ~= 0 or saturation ~= 0 or lightness ~= 0 then
    app.command.HueSaturation{ui=false, hue=hue, saturation=saturation, lightness=lightness}
end

_mcp_maybe_save(sprite, file)
print("OK: adjusted colors")