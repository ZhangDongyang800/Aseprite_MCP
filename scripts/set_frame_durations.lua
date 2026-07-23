-- set_frame_durations.lua：批量设置所有帧的时长
-- 参数: file (CLI 模式必需，Live 模式可省略), durations (逗号分隔的毫秒数，如 "125,125,125,125")
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
local durations_str = app.params["durations"]

if not durations_str then
    print("ERROR: durations is required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite
if _G._mcp_get_sprite then
    sprite = _G._mcp_get_sprite(file)
else
    sprite = file and app.open(file) or app.activeSprite
end
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 解析时长列表
local durations = {}
for d in durations_str:gmatch("[^,]+") do
    table.insert(durations, tonumber(d))
end

-- 逐帧设置时长（毫秒转秒）
local count = 0
for i, dur in ipairs(durations) do
    if sprite.frames[i] then
        sprite.frames[i].duration = dur / 1000.0
        count = count + 1
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: set durations for " .. count .. " frames")
