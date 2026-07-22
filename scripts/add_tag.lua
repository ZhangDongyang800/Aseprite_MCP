-- add_tag.lua：添加动画标签
-- 参数: file, name, from_frame (1-indexed), to_frame (1-indexed),
--       ani_dir (可选: "forward"/"reverse"/"ping_pong"/"ping_pong_reverse", 默认 "forward"),
--       repeats (可选, 默认 0)
-- 调用: aseprite -b --script add_tag.lua --script-param file=canvas.ase --script-param name=Walk --script-param from_frame=1 --script-param to_frame=6

local file = app.params["file"]
local name = app.params["name"]
local from_frame = tonumber(app.params["from_frame"])
local to_frame = tonumber(app.params["to_frame"])
local ani_dir = app.params["ani_dir"] or "forward"
local repeats = tonumber(app.params["repeats"] or "0")

if not file or not name or not from_frame or not to_frame then
    print("ERROR: file, name, from_frame, to_frame are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 将 1-indexed 帧号转换为 Aseprite API 的 0-indexed
local from_frame_0 = from_frame - 1
local to_frame_0 = to_frame - 1

-- 创建新标签
local tag = sprite:newTag(from_frame_0, to_frame_0)
if not tag then
    print("ERROR: failed to create tag")
    return
end

-- 设置标签名称和重复次数
tag.name = name
tag.repeats = repeats

-- 映射动画方向字符串到 AniDir 常量
if ani_dir == "forward" then
    tag.aniDir = AniDir.FORWARD
elseif ani_dir == "reverse" then
    tag.aniDir = AniDir.REVERSE
elseif ani_dir == "ping_pong" then
    tag.aniDir = AniDir.PING_PONG
elseif ani_dir == "ping_pong_reverse" then
    tag.aniDir = AniDir.PING_PONG_REVERSE
else
    -- 未知方向，默认使用 FORWARD
    tag.aniDir = AniDir.FORWARD
end

-- 保存并输出
sprite:saveAs(file)
print("OK: added tag '" .. name .. "' (frames " .. from_frame .. "-" .. to_frame .. ", " .. ani_dir .. ")")
