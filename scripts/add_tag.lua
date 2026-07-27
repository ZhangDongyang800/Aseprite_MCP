-- add_tag.lua：添加动画标签
-- 参数: file (CLI 模式必需，Live 模式可省略), name, from_frame (1-indexed), to_frame (1-indexed),
--       ani_dir (可选: "forward"/"reverse"/"ping_pong"/"ping_pong_reverse", 默认 "forward"),
--       repeats (可选, 默认 0)
-- 调用: aseprite -b --script add_tag.lua --script-param file=canvas.ase --script-param name=Walk --script-param from_frame=1 --script-param to_frame=6
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
local name = app.params["name"]
local from_frame = tonumber(app.params["from_frame"])
local to_frame = tonumber(app.params["to_frame"])
local ani_dir = app.params["ani_dir"] or "forward"
local repeats = tonumber(app.params["repeats"] or "0")

if not name or not from_frame or not to_frame then
    print("ERROR: name, from_frame, to_frame are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
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

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: added tag '" .. name .. "' (frames " .. from_frame .. "-" .. to_frame .. ", " .. ani_dir .. ")")
