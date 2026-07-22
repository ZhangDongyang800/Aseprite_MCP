-- resize_palette.lua：调整调色板大小（颜色数量）
-- 参数: file (会话 .ase 路径), size (新的颜色数量)
-- 调用: aseprite -b --script resize_palette.lua --script-param file=canvas.ase --script-param size=32

local file = app.params["file"]
local size = tonumber(app.params["size"])

if not file or not size then
    print("ERROR: file and size are required")
    return
end

-- 参数校验：size 必须为正整数
if size < 0 then
    print("ERROR: size must be non-negative")
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

-- 调整调色板大小
pal:resize(size)

-- 保存并输出
sprite:saveAs(file)
print("OK: resized palette to " .. size .. " colors")
