-- set_palette_color.lua：设置调色板指定索引的颜色
-- 参数: file (会话 .ase 路径), index (0-based), color (#RRGGBB 格式)
-- 调用: aseprite -b --script set_palette_color.lua --script-param file=canvas.ase --script-param index=0 --script-param color=#FF0000

local file = app.params["file"]
local index = tonumber(app.params["index"])
local color_hex = app.params["color"]

if not file or not index or not color_hex then
    print("ERROR: file, index, color are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 获取精灵调色板
local pal = sprite.palettes[1]
if not pal then
    print("ERROR: no palette found")
    return
end

-- 检查索引是否越界
if index < 0 or index >= #pal then
    print("ERROR: index out of range (0-" .. (#pal - 1) .. ")")
    return
end

-- 解析十六进制颜色 #RRGGBB
local r = tonumber(color_hex:sub(2, 3), 16)
local g = tonumber(color_hex:sub(4, 5), 16)
local b = tonumber(color_hex:sub(6, 7), 16)

-- 设置调色板颜色（alpha 固定为 255）
pal:setColor(index, Color{r=r, g=g, b=b, a=255})

-- 保存并输出
sprite:saveAs(file)
print("OK: set palette color at index " .. index .. " to " .. color_hex)
