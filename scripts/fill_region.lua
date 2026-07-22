-- fill_region.lua：油漆桶填充连通区域
-- 参数: file, x, y, color
-- 使用洪水填充算法填充与 (x,y) 相同颜色的连通区域
-- 调用: aseprite -b --script fill_region.lua --script-param file=canvas.ase --script-param x=5 --script-param y=5 --script-param color=#FF0000

local file = app.params["file"]
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])
local color_hex = app.params["color"]

if not file or not x or not y or not color_hex then
    print("ERROR: file, x, y, color are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 解析目标颜色
local r = tonumber(color_hex:sub(2, 3), 16)
local g = tonumber(color_hex:sub(4, 5), 16)
local b = tonumber(color_hex:sub(6, 7), 16)
local fill_color = app.pixelColor.rgba(r, g, b, 255)

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
local w = sprite.width
local h = sprite.height

-- 获取目标位置当前颜色
local target_color = image:getPixel(x, y)

-- 如果目标颜色与填充颜色相同，不操作
if target_color == fill_color then
    print("OK: target color matches fill color, no change")
    return
end

-- 洪水填充（使用栈避免递归溢出）
local stack = {{x, y}}
while #stack > 0 do
    local point = table.remove(stack)
    local px, py = point[1], point[2]

    -- 边界检查
    if px >= 0 and px < w and py >= 0 and py < h then
        if image:getPixel(px, py) == target_color then
            image:drawPixel(px, py, fill_color)
            table.insert(stack, {px + 1, py})
            table.insert(stack, {px - 1, py})
            table.insert(stack, {px, py + 1})
            table.insert(stack, {px, py - 1})
        end
    end
end

sprite:saveAs(file)
print("OK: filled region from (" .. x .. "," .. y .. ")")
