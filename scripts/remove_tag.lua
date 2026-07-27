-- remove_tag.lua：按名称移除动画标签
-- 参数: file (CLI 模式必需，Live 模式可省略), name (标签名称)
-- 调用: aseprite -b --script remove_tag.lua --script-param file=canvas.ase --script-param name=Walk
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 修改实时反映在 Aseprite UI 上
-- CLI 模式行为：
--   - 从 file 打开 sprite，修改后保存回 file

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local name = app.params["name"]

if not name then
    print("ERROR: name is required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
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

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: removed tag '" .. name .. "'")
