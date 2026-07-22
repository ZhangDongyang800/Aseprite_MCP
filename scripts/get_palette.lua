-- get_palette.lua：获取当前调色板信息
-- 参数: file (会话 .ase 路径)
-- 输出: JSON 字符串，包含 colors 数组和 size
-- 调用: aseprite -b --script get_palette.lua --script-param file=canvas.ase

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

-- 获取精灵调色板
local pal = sprite.palettes[1]
if not pal then
    print('{"error": "no palette found"}')
    return
end

-- 遍历调色板，构建颜色数组
local colors = {}
for i = 0, #pal - 1 do
    local c = pal:getColor(i)
    -- 格式化为 #RRGGBB
    local hex = string.format("#%02X%02X%02X", c.red, c.green, c.blue)
    table.insert(colors, '"' .. hex .. '"')
end

-- 输出 JSON
local json = '{"colors": [' .. table.concat(colors, ", ") .. '], "size": ' .. #pal .. '}'
print(json)
