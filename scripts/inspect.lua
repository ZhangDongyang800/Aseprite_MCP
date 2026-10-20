-- inspect.lua: read-only perception. Always scales/exports on a temp copy (fixes P0-1).
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

local file = app.params["file"]
local output = app.params["output"]
local metrics_output = app.params["metrics_output"]
local scale = tonumber(app.params["scale"] or "4") or 4
local view = app.params["view"] or "composite"
local want = tonumber(app.params["frame"] or "1") or 1

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
    -- Frame.duration is already seconds, the same unit add_frames/set_durations take: report as is
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

-- Temp copy: neither the resize nor the export ever touches the original document
local preview = Sprite(sprite)

-- On a multi-frame document saveCopyAs writes name1.png..nameN.png, never the agreed name.
-- Collapse the copy to frame `want` first; the original document keeps all its frames.
if want < 1 then want = 1 end
if want > #preview.frames then want = #preview.frames end
for i = #preview.frames, 1, -1 do
  if i ~= want then preview:deleteFrame(preview.frames[i]) end
end

-- First save a scale=1 copy at native size for Python's metrics (no upscale/recolour skew)
if metrics_output and metrics_output ~= "" then
    preview:saveCopyAs(metrics_output)
end

-- silhouette view: paint every non-transparent pixel of the copy black (copy only)
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

-- The upscaled preview must be capped: a 4096² canvas at scale=4 is 160M pixels, so one
-- inspect eats all the memory and bandwidth and then stuffs an unreadable image into the chat.
local MAX_PREVIEW_PIXELS = 4194304  -- 2048x2048
local applied_scale = scale
if scale > 1 then
    local pw, ph = preview.width, preview.height
    local wanted = pw * scale * ph * scale
    if wanted > MAX_PREVIEW_PIXELS then
        local factor = math.sqrt(MAX_PREVIEW_PIXELS / (pw * ph))
        applied_scale = math.max(1, math.floor(factor))
    end
    if applied_scale > 1 then
        preview:resize(pw * applied_scale, ph * applied_scale)
    end
end
preview:saveCopyAs(output)
preview:close()

print(json.encode({
    width = sprite.width, height = sprite.height,
    frames = frames, layers = layers, palette = palette, tags = tags, view = view,
    frame = want, frames_total = #sprite.frames,
    scale = applied_scale, scale_clamped = applied_scale ~= scale,
}))
