-- remove_tag.lua：按名称移除动画标签
-- 参数: file, name (标签名称)
-- 调用: aseprite -b --script remove_tag.lua --script-param file=canvas.ase --script-param name=Walk

local file = app.params["file"]
local name = app.params["name"]

if not file or not name then
    print("ERROR: file and name are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 按名称查找并删除标签（deleteTag 接受标签对象而非名称字符串）
local found = false
for i, tag in ipairs(sprite.tags) do
    if tag.name == name then
        sprite:deleteTag(tag)
        found = true
        break
    end
end

if not found then
    print("ERROR: tag '" .. name .. "' not found")
    return
end

-- 保存并输出
sprite:saveAs(file)
print("OK: removed tag '" .. name .. "'")
