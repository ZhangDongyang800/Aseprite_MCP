-- set_frame_durations.lua：批量设置所有帧的时长
-- 参数: file, durations (逗号分隔的毫秒数，如 "125,125,125,125")
local file = app.params["file"]
local durations_str = app.params["durations"]

if not file or not durations_str then
    print("ERROR: file and durations are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
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

sprite:saveAs(file)
print("OK: set durations for " .. count .. " frames")
