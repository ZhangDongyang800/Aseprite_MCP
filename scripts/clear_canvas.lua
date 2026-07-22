-- clear_canvas.lua：清空整个画布
-- 参数: file
-- 调用: aseprite -b --script clear_canvas.lua --script-param file=canvas.ase

local file = app.params["file"]

if not file then
    print("ERROR: file is required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 透明像素颜色
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

-- 清除所有像素
for y = 0, sprite.height - 1 do
    for x = 0, sprite.width - 1 do
        image:drawPixel(x, y, transparent)
    end
end

sprite:saveAs(file)
print("OK: cleared canvas")
