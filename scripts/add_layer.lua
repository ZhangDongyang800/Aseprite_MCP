-- add_layer.lua：添加新图层
-- 参数: file, name (可选，默认 "Layer")
-- 调用: aseprite -b --script add_layer.lua --script-param file=canvas.ase --script-param name=Background

local file = app.params["file"]
-- 图层名称，未提供时使用默认值
local name = app.params["name"] or "Layer"

if not file then
    print("ERROR: file is required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 创建新图层并设置名称
local layer = sprite:newLayer()
layer.name = name

sprite:saveAs(file)
print("OK: added layer '" .. name .. "'")
