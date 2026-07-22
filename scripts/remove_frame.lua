-- remove_frame.lua：删除指定帧
-- 参数: file, frame (要删除的帧号, 1-indexed)
-- 调用: aseprite -b --script remove_frame.lua --script-param file=canvas.ase --script-param frame=2

local file = app.params["file"]
local frame = tonumber(app.params["frame"])

if not file then
    print("ERROR: file is required")
    return
end

if not frame then
    print("ERROR: frame is required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 验证帧号是否存在
if frame < 1 or frame > #sprite.frames then
    print("ERROR: frame " .. frame .. " does not exist (total frames: " .. #sprite.frames .. ")")
    return
end

-- 删除指定帧
sprite:deleteFrame(sprite.frames[frame])

sprite:saveAs(file)
print("OK: removed frame " .. frame)
