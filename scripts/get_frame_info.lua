-- get_frame_info.lua：获取所有帧信息，输出 JSON 格式
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略)
-- 输出: JSON 字符串，包含 frame_count 和 frames 数组（每帧含 frame_number 和 duration）
-- 调用: aseprite -b --script get_frame_info.lua --script-param file=canvas.ase
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
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print('{"error": "no active sprite. Call create_sprite first, or provide file parameter."}')
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
