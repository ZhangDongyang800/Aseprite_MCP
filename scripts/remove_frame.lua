-- remove_frame.lua：删除指定帧
-- 参数: file (CLI 模式必需，Live 模式可省略), frame (要删除的帧号, 1-indexed)
-- 调用: aseprite -b --script remove_frame.lua --script-param file=canvas.ase --script-param frame=2
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
local frame = tonumber(app.params["frame"])

if not frame then
    print("ERROR: frame is required")
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

-- 验证帧号是否存在
if frame < 1 or frame > #sprite.frames then
    print("ERROR: frame " .. frame .. " does not exist (total frames: " .. #sprite.frames .. ")")
    return
end

-- 删除指定帧
sprite:deleteFrame(sprite.frames[frame])

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: removed frame " .. frame)
