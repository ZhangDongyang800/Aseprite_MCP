-- draw_ellipse.lua：画椭圆（空心或实心）
-- 参数: file, cx (中心 x), cy (中心 y), rx (x 半径), ry (y 半径), color, filled
-- 调用: aseprite -b --script draw_ellipse.lua --script-param file=canvas.ase --script-param cx=8 --script-param cy=8 --script-param rx=5 --script-param ry=5 --script-param color=#FF0000 --script-param filled=true

local file = app.params["file"]
local cx = tonumber(app.params["cx"])
local cy = tonumber(app.params["cy"])
local rx = tonumber(app.params["rx"])
local ry = tonumber(app.params["ry"])
local color_hex = app.params["color"]
local filled = app.params["filled"] == "true"

if not file or not cx or not cy or not rx or not ry or not color_hex then
    print("ERROR: file, cx, cy, rx, ry, color are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 解析颜色
local r = tonumber(color_hex:sub(2, 3), 16)
local g = tonumber(color_hex:sub(4, 5), 16)
local b = tonumber(color_hex:sub(6, 7), 16)
local pixel_color = app.pixelColor.rgba(r, g, b, 255)

local cel = sprite.cels[1]
local image = cel.image

-- 使用中点椭圆算法
if filled then
    -- 实心椭圆：逐行扫描
    for py = cy - ry, cy + ry do
        local dy = py - cy
        local half_width = math.floor(rx * math.sqrt(1 - (dy * dy) / (ry * ry) + 0.5))
        for px = cx - half_width, cx + half_width do
            image:drawPixel(px, py, pixel_color)
        end
    end
else
    -- 空心椭圆：只画轮廓
    for py = cy - ry, cy + ry do
        local dy = py - cy
        local half_width = math.floor(rx * math.sqrt(1 - (dy * dy) / (ry * ry) + 0.5))
        if half_width >= 0 then
            image:drawPixel(cx - half_width, py, pixel_color)
            image:drawPixel(cx + half_width, py, pixel_color)
        end
    end
end

sprite:saveAs(file)
print("OK: drew ellipse at (" .. cx .. "," .. cy .. ") rx=" .. rx .. " ry=" .. ry .. " filled=" .. tostring(filled))
