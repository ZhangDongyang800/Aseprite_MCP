-- tween_cel.lua：图层 cel 的补间（线性插值）
-- 参数: file (CLI 模式必需，Live 模式可省略), layer (索引或名称),
--       from_frame (1-based), to_frame (1-based，须 > from_frame),
--       property (pos / opacity / scale), 以及对应的起止值:
--         pos:     start_x, start_y, end_x, end_y（cel 左上角坐标）
--         opacity: start_opacity, end_opacity（0-255）
--         scale:   start_scale, end_scale（相对 from_frame 原始尺寸的比例）
--
-- 用途: 挥剑轨迹、移动、呼吸起伏、淡入淡出。帧间数值由构造保证线性，
--       不会出现手绘补间常见的抖动。

if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end

local file = app.params["file"]
local layer_param = app.params["layer"]
local from_frame = tonumber(app.params["from_frame"] or "1")
local to_frame = tonumber(app.params["to_frame"] or "2")
local property = app.params["property"] or "pos"

local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

if not layer_param then
    print("ERROR: layer is required")
    return
end

local layer
local num = tonumber(layer_param)
if num then
    layer = sprite.layers[num]
else
    for _, l in ipairs(sprite.layers) do
        if l.name == layer_param then layer = l break end
    end
end

if not layer then
    print("ERROR: layer not found: " .. layer_param)
    return
end

local frame_count = #sprite.frames
if from_frame < 1 or to_frame < 1 or from_frame > frame_count or to_frame > frame_count then
    print("ERROR: from_frame/to_frame out of range. frame count = " .. frame_count)
    return
end
if to_frame <= from_frame then
    print("ERROR: to_frame must be > from_frame")
    return
end

-- 线性插值
local function lerp(a, b, t)
    return a + (b - a) * t
end

-- 取 from_frame 的 cel 作为基准（scale 需要原始尺寸）
local source_cel = layer:cel(from_frame)
if not source_cel then
    print("ERROR: no cel at layer '" .. layer.name .. "' frame " .. from_frame)
    return
end

local orig_w = source_cel.image.width
local orig_h = source_cel.image.height
local orig_pos_x = source_cel.position.x
local orig_pos_y = source_cel.position.y

local processed = 0
for f = from_frame, to_frame do
    local cel = layer:cel(f)
    if cel then
        local t = (f - from_frame) / (to_frame - from_frame)
        if property == "pos" then
            local x = math.floor(lerp(tonumber(app.params["start_x"]) or 0,
                                      tonumber(app.params["end_x"]) or 0, t) + 0.5)
            local y = math.floor(lerp(tonumber(app.params["start_y"]) or 0,
                                      tonumber(app.params["end_y"]) or 0, t) + 0.5)
            cel.position = Point(x, y)
        elseif property == "opacity" then
            local o = math.floor(lerp(tonumber(app.params["start_opacity"]) or 255,
                                      tonumber(app.params["end_opacity"]) or 255, t) + 0.5)
            cel.opacity = math.max(0, math.min(255, o))
        elseif property == "scale" then
            local s = lerp(tonumber(app.params["start_scale"]) or 1,
                           tonumber(app.params["end_scale"]) or 1, t)
            local new_w = math.max(1, math.floor(orig_w * s + 0.5))
            local new_h = math.max(1, math.floor(orig_h * s + 0.5))
            -- 以原始中心为锚点：尺寸变化时平移 position 保持居中
            local dx = math.floor((orig_w - new_w) / 2 + 0.5)
            local dy = math.floor((orig_h - new_h) / 2 + 0.5)
            cel.position = Point(orig_pos_x + dx, orig_pos_y + dy)
            cel:resize(new_w, new_h)
        else
            print("ERROR: property must be pos/opacity/scale")
            return
        end
        processed = processed + 1
    end
end

_mcp_maybe_save(sprite, file)
print(string.format(
    "OK: tweened cel '%s' property=%s frames %d-%d (%d cels)",
    layer.name, property, from_frame, to_frame, processed
))
