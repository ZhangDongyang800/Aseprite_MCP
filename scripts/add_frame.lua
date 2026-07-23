-- add_frame.lua：添加新帧（复制最后一帧或创建空白帧）
-- 参数: file (CLI 模式必需，Live 模式可省略), frame (可选, 默认=最后一帧+1), content (可选: "empty" 或 "copy", 默认 "copy")
-- 调用: aseprite -b --script add_frame.lua --script-param file=canvas.ase --script-param content=copy
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
local frame = app.params["frame"]          -- 可选，帧号（1-indexed）
local content = app.params["content"] or "copy"  -- 默认复制最后一帧

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

-- 确定帧号（默认为最后一帧 + 1）
local frame_number
if frame then
    frame_number = tonumber(frame)
else
    frame_number = #sprite.frames + 1
end

-- 根据内容类型添加帧
if content == "copy" then
    -- 复制最后一帧的内容
    if #sprite.frames > 0 then
        sprite:newFrame(sprite.frames[#sprite.frames])
        frame_number = #sprite.frames  -- 新帧号 = 添加后的最后一帧
    else
        -- 没有帧时创建空白帧
        sprite:newEmptyFrame(frame_number)
    end
elseif content == "empty" then
    -- 创建空白帧
    sprite:newEmptyFrame(frame_number)
else
    print("ERROR: content must be 'empty' or 'copy'")
    return
end

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: added frame " .. frame_number .. " (content=" .. content .. ")")
