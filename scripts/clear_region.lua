-- clear_region.lua：清除指定区域为透明
-- 参数: file, x, y, width, height
-- 调用: aseprite -b --script clear_region.lua --script-param file=canvas.ase --script-param x=0 --script-param y=0 --script-param width=5 --script-param height=5

local file = app.params["file"]
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])
local w = tonumber(app.params["width"])
local h = tonumber(app.params["height"])

if not file or not x or not y or not w or not h then
    print("ERROR: file, x, y, width, height are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 透明像素颜色（alpha=0）
local transparent = app.pixelColor.rgba(0, 0, 0, 0)

-- 支持指定图层和帧（默认第1图层第1帧）
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local target_layer = sprite.layers[layer_idx]
if not target_layer then
    print("ERROR: layer not found: " .. layer_idx)
    return
end
local cel = target_layer:cel(frame_idx)
if not cel then
    cel = sprite:newCel(target_layer, frame_idx)
end
local image = cel.image

-- 清除区域内的像素
for py = y, y + h - 1 do
    for px = x, x + w - 1 do
        if px >= 0 and px < sprite.width and py >= 0 and py < sprite.height then
            image:drawPixel(px, py, transparent)
        end
    end
end

sprite:saveAs(file)
print("OK: cleared region at (" .. x .. "," .. y .. ") " .. w .. "x" .. h)
