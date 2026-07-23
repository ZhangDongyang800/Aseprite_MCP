-- get_pixel_color.lua：查询指定像素的颜色
-- 参数: file (CLI 模式必需，Live 模式可省略，会话 .ase 路径), x, y
-- 输出: JSON 字符串，包含 hex 颜色
-- 调用: aseprite -b --script get_pixel_color.lua --script-param file=canvas.ase --script-param x=5 --script-param y=10
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
-- CLI 模式行为：
--   - 从 file 打开 sprite 读取像素颜色

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])

-- 参数校验：x、y 为必填，file 在 Live 模式下可省略
if not x or not y then
    print('{"error": "x, y are required"}')
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite
if _G._mcp_get_sprite then
    sprite = _G._mcp_get_sprite(file)
else
    sprite = file and app.open(file) or app.activeSprite
end
if not sprite then
    print('{"error": "no active sprite. Call create_sprite first, or provide file parameter."}')
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
