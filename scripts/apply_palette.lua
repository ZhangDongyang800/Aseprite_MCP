-- apply_palette.lua：整板替换调色板为指定颜色序列
-- 参数: file, colors (逗号分隔的 #RRGGBB 列表)
-- 行为: 调整调色板大小为 colors 数量，逐色写入（覆盖原调色板）
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

-- 解析颜色列表
local colors = {}
for hex in colors_str:gmatch("[^,]+") do
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    table.insert(colors, {r=r, g=g, b=b})
end

-- 调整调色板大小并写入（整板替换）
pal:resize(#colors)
for i, c in ipairs(colors) do
    pal:setColor(i - 1, Color{r=c.r, g=c.g, b=c.b, a=255})
end

sprite:saveAs(file)
print("OK: applied palette with " .. #colors .. " colors")
