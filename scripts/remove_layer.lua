-- remove_layer.lua：删除指定图层
-- 参数: file, layer (图层名称或 1-based 索引)
-- 调用: aseprite -b --script remove_layer.lua --script-param file=canvas.ase --script-param layer=Background

local file = app.params["file"]
local layer_param = app.params["layer"]

if not file or not layer_param then
    print("ERROR: file and layer are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 判断参数是数字索引还是图层名称
local num = tonumber(layer_param)
if num then
    -- 数字索引：通过索引获取图层对象后删除
    local layer = sprite.layers[num]
    if not layer then
        print("ERROR: layer index out of range: " .. layer_param)
        return
    end
    sprite:deleteLayer(layer)
else
    -- 字符串：按名称删除
    sprite:deleteLayer(layer_param)
end

sprite:saveAs(file)
print("OK: removed layer '" .. layer_param .. "'")
