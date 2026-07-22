-- create_sprite.lua：创建新精灵
-- 参数: width, height, color_mode (rgb/grayscale/indexed), file (输出路径)
-- 调用: aseprite -b --script create_sprite.lua --script-param width=16 --script-param height=16 --script-param color_mode=rgb --script-param file=canvas.ase

local width = tonumber(app.params["width"])
local height = tonumber(app.params["height"])
local color_mode = app.params["color_mode"] or "rgb"
local file = app.params["file"]

if not width or not height then
    print("ERROR: width and height are required")
    return
end

-- 映射颜色模式字符串到 ColorMode 常量
local mode
if color_mode == "rgb" then
    mode = ColorMode.RGB
elseif color_mode == "grayscale" then
    mode = ColorMode.GRAYSCALE
elseif color_mode == "indexed" then
    mode = ColorMode.INDEXED
else
    print("ERROR: unknown color_mode: " .. color_mode)
    return
end

-- 创建新精灵
local sprite = Sprite(width, height, mode)
if not sprite then
    print("ERROR: failed to create sprite")
    return
end

-- 保存到指定路径
sprite:saveAs(file)
print("OK: created sprite " .. width .. "x" .. height .. " " .. color_mode .. " at " .. file)
