-- append_palette.lua：批量追加颜色到调色板末尾
-- 参数: file, colors (逗号分隔的 #RRGGBB 列表)
-- 行为: 在现有调色板末尾追加颜色，不覆盖已有颜色
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

-- 计算当前调色板大小，追加颜色
local start_index = #pal
local count = 0
for hex in colors_str:gmatch("[^,]+") do
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    -- addColor 追加到末尾
    pal:addColor(Color{r=r, g=g, b=b, a=255})
    count = count + 1
end

sprite:saveAs(file)
print("OK: appended " .. count .. " colors to palette (now " .. #pal .. " total)")
