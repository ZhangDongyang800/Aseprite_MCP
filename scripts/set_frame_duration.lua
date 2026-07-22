-- set_frame_duration.lua：设置帧持续时间
-- 参数: file, frame (1-indexed), duration (秒, 浮点数)
-- 调用: aseprite -b --script set_frame_duration.lua --script-param file=canvas.ase --script-param frame=1 --script-param duration=0.1

local file = app.params["file"]
local frame = tonumber(app.params["frame"])
local duration = tonumber(app.params["duration"])

if not file then
    print("ERROR: file is required")
    return
end

if not frame or not duration then
    print("ERROR: frame and duration are required")
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

-- 设置帧持续时间（单位：秒）
sprite.frames[frame].duration = duration

sprite:saveAs(file)
print("OK: set frame " .. frame .. " duration to " .. duration .. "s")
