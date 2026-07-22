-- get_canvas_info.lua：获取画布元数据，输出 JSON 格式
-- 参数: file (会话 .ase 路径)
-- 输出: JSON 字符串，包含 width, height, color_mode, frames
-- 调用: aseprite -b --script get_canvas_info.lua --script-param file=canvas.ase

local file = app.params["file"]

if not file then
    print('{"error": "file is required"}')
    return
end

local sprite = app.open(file)
if not sprite then
    print('{"error": "cannot open file: ' .. file .. '"}')
    return
end

-- 获取颜色模式名称
local mode_name
if sprite.colorMode == ColorMode.RGB then
    mode_name = "rgb"
elseif sprite.colorMode == ColorMode.GRAYSCALE then
    mode_name = "grayscale"
elseif sprite.colorMode == ColorMode.INDEXED then
    mode_name = "indexed"
else
    mode_name = "unknown"
end

-- 输出 JSON
local json = string.format(
    '{"width": %d, "height": %d, "color_mode": "%s", "frames": %d}',
    sprite.width, sprite.height, mode_name, #sprite.frames
)
print(json)
