-- get_palette.lua：获取当前调色板信息
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略)
-- 输出: JSON 字符串，包含 colors 数组和 size
-- 调用: aseprite -b --script get_palette.lua --script-param file=canvas.ase
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
-- CLI 模式行为：
--   - 从 file 打开 sprite（只读，不保存）

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print('{"error": "no active sprite. Call create_sprite first, or provide file parameter."}')
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
