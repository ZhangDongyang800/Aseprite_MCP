-- draw_rect.lua：画矩形（空心或实心）
-- 参数: file, x, y, width, height, color, filled (true/false，默认 false)
-- 调用: aseprite -b --script draw_rect.lua --script-param file=canvas.ase --script-param x=0 --script-param y=0 --script-param width=10 --script-param height=10 --script-param color=#FF0000 --script-param filled=true

local file = app.params["file"]
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])
local w = tonumber(app.params["width"])
local h = tonumber(app.params["height"])
local color_hex = app.params["color"]
local filled = app.params["filled"] == "true"

if not file or not x or not y or not w or not h or not color_hex then
    print("ERROR: file, x, y, width, height, color are required")
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

if filled then
    -- 实心矩形
    for py = y, y + h - 1 do
        for px = x, x + w - 1 do
            image:drawPixel(px, py, pixel_color)
        end
    end
else
    -- 空心矩形（只画边框）
    for px = x, x + w - 1 do
        image:drawPixel(px, y, pixel_color)             -- 上边
        image:drawPixel(px, y + h - 1, pixel_color)     -- 下边
    end
    for py = y, y + h - 1 do
        image:drawPixel(x, py, pixel_color)             -- 左边
        image:drawPixel(x + w - 1, py, pixel_color)     -- 右边
    end
end

sprite:saveAs(file)
print("OK: drew rect at (" .. x .. "," .. y .. ") " .. w .. "x" .. h .. " filled=" .. tostring(filled))
