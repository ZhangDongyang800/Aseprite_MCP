-- draw_pixel.lua：在指定坐标画一个像素
-- 参数: file, x, y, color (#RRGGBB 格式)
-- 调用: aseprite -b --script draw_pixel.lua --script-param file=canvas.ase --script-param x=10 --script-param y=20 --script-param color=#FF0000

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

-- 解析十六进制颜色
local r = tonumber(color_hex:sub(2, 3), 16)
local g = tonumber(color_hex:sub(4, 5), 16)
local b = tonumber(color_hex:sub(6, 7), 16)
local pixel_color = app.pixelColor.rgba(r, g, b, 255)

-- 在当前图层当前帧画像素
local cel = sprite.cels[1]
local image = cel.image
image:drawPixel(x, y, pixel_color)

sprite:saveAs(file)
print("OK: drew pixel at (" .. x .. "," .. y .. ")")
