-- append_palette.lua：批量追加颜色到调色板末尾
-- 参数: file (CLI 模式必需，Live 模式可省略), colors (逗号分隔的 #RRGGBB 列表)
-- 行为: 在现有调色板末尾追加颜色，不覆盖已有颜色
-- 实现: 用 resize+setColor 替代 addColor（addColor 在 RGB/indexed 模式下行为不稳定）
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 修改实时反映在 Aseprite UI 上
-- CLI 模式行为：
--   - 从 file 打开 sprite，修改后保存回 file

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local colors_str = app.params["colors"]

if not colors_str then
    print("ERROR: colors are required")
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
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

local pal = sprite.palettes[1]
if not pal then
    print("ERROR: no palette found")
    return
end

-- 先解析颜色列表，计算数量
local colors = {}
for hex in colors_str:gmatch("[^,]+") do
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    table.insert(colors, {r=r, g=g, b=b})
end

-- 用 resize 扩展调色板，再用 setColor 写入（比 addColor 更可靠）
local old_size = #pal
pal:resize(old_size + #colors)
for i, c in ipairs(colors) do
    pal:setColor(old_size + i - 1, Color{r=c.r, g=c.g, b=c.b, a=255})
end

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: appended " .. #colors .. " colors to palette (now " .. #pal .. " total)")
