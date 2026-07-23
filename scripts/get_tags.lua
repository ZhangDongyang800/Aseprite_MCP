-- get_tags.lua：获取所有动画标签
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略)
-- 输出: JSON 数组，包含每个标签的名称、帧范围、动画方向、重复次数
-- 调用: aseprite -b --script get_tags.lua --script-param file=canvas.ase
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
-- CLI 模式行为：
--   - 从 file 打开 sprite（只读，不保存）

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite
if _G._mcp_get_sprite then
    sprite = _G._mcp_get_sprite(file)
else
    sprite = file and app.open(file) or app.activeSprite
end
if not sprite then
    print('{"error": "no active sprite. Call create_sprite first, or provide file parameter."}')
    return
end

-- 反向映射 AniDir 常量到字符串
local function ani_dir_to_string(dir)
    if dir == AniDir.FORWARD then
        return "forward"
    elseif dir == AniDir.REVERSE then
        return "reverse"
    elseif dir == AniDir.PING_PONG then
        return "ping_pong"
    elseif dir == AniDir.PING_PONG_REVERSE then
        return "ping_pong_reverse"
    else
        -- 未知方向，默认返回 forward
        return "forward"
    end
end

-- 遍历标签，构建 JSON 数组
local items = {}
for i, tag in ipairs(sprite.tags) do
    -- 将 0-indexed 帧号转换为 1-indexed 输出，与 add_tag 的输入保持一致
    local item = string.format(
        '{"name": "%s", "from_frame": %d, "to_frame": %d, "ani_dir": "%s", "repeats": %d}',
        tag.name, tag.fromFrame + 1, tag.toFrame + 1,
        ani_dir_to_string(tag.aniDir), tag.repeats
    )
    table.insert(items, item)
end

-- 输出 JSON 数组（空列表时输出 []）
local json = '[' .. table.concat(items, ", ") .. ']'
print(json)
