-- append_palette.lua：批量追加颜色到调色板末尾
-- 参数: file, colors (逗号分隔的 #RRGGBB 列表)
-- 行为: 在现有调色板末尾追加颜色，不覆盖已有颜色
-- 实现: 用 resize+setColor 替代 addColor（addColor 在 RGB/indexed 模式下行为不稳定）
local file = app.params["file"]
local colors_str = app.params["colors"]

if not file or not colors_str then
    print("ERROR: file and colors are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
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

sprite:saveAs(file)
print("OK: appended " .. #colors .. " colors to palette (now " .. #pal .. " total)")
