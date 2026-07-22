-- export_tiled.lua：把当前画布当单个瓦片，导出 repeat×repeat 拼接预览 PNG
-- 参数: file, output, repeat (重复次数，默认 2), scale (默认 1)
local file = app.params["file"]
local output = app.params["output"]
local rep = tonumber(app.params["repeat"] or "2")
local scale = tonumber(app.params["scale"] or "1")

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

local w = sprite.width
local h = sprite.height
local layer = sprite.layers[1]
local cel = layer:cel(1)
if not cel or not cel.image then
    print("ERROR: no image in frame 1")
    return
end
local src = cel.image

-- 创建拼接后的画布
local out_w = w * rep
local out_h = h * rep
local result = Image(out_w, out_h, sprite.colorMode)
result:clear()

-- 平铺复制
for ry = 0, rep - 1 do
    for rx = 0, rep - 1 do
        result:drawImage(src, rx * w, ry * h)
    end
end

-- 导出
local tmp_sprite = Sprite(out_w, out_h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(result)
if scale > 1 then
    tmp_sprite:resize(out_w * scale, out_h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print("OK: exported tiled preview " .. rep .. "x" .. rep .. " to " .. output)
