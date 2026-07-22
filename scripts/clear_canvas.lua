-- clear_canvas.lua：清空整个画布
-- 参数: file
-- 调用: aseprite -b --script clear_canvas.lua --script-param file=canvas.ase

local file = app.params["file"]

if not file then
    print("ERROR: file is required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 透明像素颜色
local transparent = app.pixelColor.rgba(0, 0, 0, 0)

local cel = sprite.cels[1]
local image = cel.image

-- 清除所有像素
for y = 0, sprite.height - 1 do
    for x = 0, sprite.width - 1 do
        image:drawPixel(x, y, transparent)
    end
end

sprite:saveAs(file)
print("OK: cleared canvas")
