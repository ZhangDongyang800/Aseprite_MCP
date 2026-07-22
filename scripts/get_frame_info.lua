-- get_frame_info.lua：获取所有帧信息，输出 JSON 格式
-- 参数: file (会话 .ase 路径)
-- 输出: JSON 字符串，包含 frame_count 和 frames 数组（每帧含 frame_number 和 duration）
-- 调用: aseprite -b --script get_frame_info.lua --script-param file=canvas.ase

local file = app.params["file"]

if not file then
    print('{"error": "file is required"}')
    return
end

local sprite = app.open(file)
if not sprite then
    print('{"error": "cannot open file: ' .. file .. '"}')
    return
end

-- 构建 frames 数组的 JSON 片段
local frames_json = {}
for i = 1, #sprite.frames do
    local f = sprite.frames[i]
    -- 每帧输出帧号和持续时间（单位：秒）
    local frame_str = string.format(
        '{"frame_number": %d, "duration": %.6f}',
        i, f.duration
    )
    table.insert(frames_json, frame_str)
end

-- 输出完整 JSON
local json = string.format(
    '{"frame_count": %d, "frames": [%s]}',
    #sprite.frames, table.concat(frames_json, ", ")
)
print(json)
