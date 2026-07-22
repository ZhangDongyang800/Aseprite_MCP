-- get_pixel_color.lua：查询指定像素的颜色
-- 参数: file (会话 .ase 路径), x, y
-- 输出: JSON 字符串，包含 hex 颜色
-- 调用: aseprite -b --script get_pixel_color.lua --script-param file=canvas.ase --script-param x=5 --script-param y=10

local file = app.params["file"]
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])

if not file or not x or not y then
    print('{"error": "file, x, y are required"}')
    return
end

local sprite = app.open(file)
if not sprite then
    print('{"error": "cannot open file: ' .. file .. '"}')
    return
end

-- 获取第一个 cel 的图像
local cel = sprite.cels[1]
if not cel then
    print('{"error": "no cel found"}')
    return
end

local image = cel.image

-- 检查坐标是否在画布范围内
if x < 0 or x >= sprite.width or y < 0 or y >= sprite.height then
    print('{"error": "coordinates out of bounds"}')
    return
end

-- 获取像素颜色
local pixel_value = image:getPixel(x, y)

-- 解析 RGBA 分量
local r = app.pixelColor.rgbaR(pixel_value)
local g = app.pixelColor.rgbaG(pixel_value)
local b = app.pixelColor.rgbaB(pixel_value)
local a = app.pixelColor.rgbaA(pixel_value)

-- 格式化为十六进制
local hex = string.format("#%02X%02X%02X", r, g, b)

-- 输出 JSON
local json = string.format(
    '{"x": %d, "y": %d, "hex": "%s", "r": %d, "g": %d, "b": %d, "a": %d}',
    x, y, hex, r, g, b, a
)
print(json)
