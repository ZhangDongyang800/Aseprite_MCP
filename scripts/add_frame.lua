-- add_frame.lua：添加新帧（复制最后一帧或创建空白帧）
-- 参数: file, frame (可选, 默认=最后一帧+1), content (可选: "empty" 或 "copy", 默认 "copy")
-- 调用: aseprite -b --script add_frame.lua --script-param file=canvas.ase --script-param content=copy

local file = app.params["file"]
local frame = app.params["frame"]          -- 可选，帧号（1-indexed）
local content = app.params["content"] or "copy"  -- 默认复制最后一帧

if not file then
    print("ERROR: file is required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
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

sprite:saveAs(file)
print("OK: added frame " .. frame_number .. " (content=" .. content .. ")")
