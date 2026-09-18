-- inspect.lua：只读感知。永远在临时副本上缩放/导出（修 P0-1）。
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

local file = app.params["file"]
local output = app.params["output"]
local metrics_output = app.params["metrics_output"]
local scale = tonumber(app.params["scale"] or "4") or 4
local view = app.params["view"] or "composite"

if not output then error("output is required") end
if not metrics_output or metrics_output == "" then error("metrics_output is required") end

local sprite = _G._mcp_get_sprite(file)
if not sprite then error("no sprite. Call create_sprite first.") end

local layers = {}
for i, layer in ipairs(sprite.layers) do
    layers[i] = {name = layer.name, visible = layer.isVisible, opacity = layer.opacity}
end
local frames = {}
for i, frame in ipairs(sprite.frames) do
    frames[i] = {number = i, duration = frame.duration}
end
local palette = {}
for i = 0, #sprite.palettes[1] - 1 do
    local c = sprite.palettes[1]:getColor(i)
    palette[i + 1] = string.format("#%02X%02X%02X", c.red, c.green, c.blue)
end
local tags = {}
for i, tag in ipairs(sprite.tags) do
    tags[i] = {name = tag.name, from = tag.fromFrame.frameNumber, to = tag.toFrame.frameNumber}
end

-- 临时副本：缩放与导出都不触碰原文档
local preview = Sprite(sprite)

-- 先落一张 scale=1 原始尺寸副本供 Python 计算指标（避免放大/recolour 失真）
if metrics_output and metrics_output ~= "" then
    preview:saveCopyAs(metrics_output)
end

-- silhouette 视图：把副本上所有非透明像素涂黑（仅改副本）
if view == "silhouette" then
    local black = app.pixelColor.rgba(0, 0, 0, 255)
    for _, layer in ipairs(preview.layers) do
        for _, cel in ipairs(layer.cels) do
            local img = cel.image
            for y = 0, img.height - 1 do
                for x = 0, img.width - 1 do
                    local c = img:getPixel(x, y)
                    if app.pixelColor.rgbaA(c) > 0 then
                        img:drawPixel(x, y, black)
                    end
                end
            end
        end
    end
end

if scale > 1 then
    preview:resize(preview.width * scale, preview.height * scale)
end
preview:saveCopyAs(output)
preview:close()

print(json.encode({
    width = sprite.width, height = sprite.height,
    frames = frames, layers = layers, palette = palette, tags = tags, view = view,
}))
