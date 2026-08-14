-- propagate_cels.lua：把某帧某图层的 cel 复制到后续帧范围
-- 参数: file (CLI 模式必需，Live 模式可省略), layer (索引或名称), source_frame (1-based),
--       to_frame (1-based，包含，须 > source_frame)
--
-- 用途: "换姿势不换画"工作流核心：先画好基础身体/背景层，复制到整个帧范围，
--       肢体层再逐帧独立编辑。保证静态部分帧间零差异。
--
-- 调用: aseprite -b --script propagate_cels.lua --script-param file=canvas.ase
--   --script-param layer=1 --script-param source_frame=1 --script-param to_frame=4

if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end

local file = app.params["file"]
local layer_param = app.params["layer"]
local source_frame = tonumber(app.params["source_frame"] or "1")
local to_frame = tonumber(app.params["to_frame"] or "0")

local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

if not layer_param then
    print("ERROR: layer is required")
    return
end

-- 按名称或索引查找图层
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
if to_frame == 0 or to_frame > frame_count then to_frame = frame_count end
if source_frame < 1 or source_frame > frame_count then
    print("ERROR: source_frame out of range: " .. source_frame)
    return
end
if to_frame <= source_frame then
    print("ERROR: to_frame must be > source_frame")
    return
end

local source_cel = layer:cel(source_frame)
if not source_cel or not source_cel.image then
    print("ERROR: no cel at layer '" .. layer.name .. "' frame " .. source_frame)
    return
end

local source_image = source_cel.image
local pos = source_cel.position

for f = source_frame + 1, to_frame do
    local cel = layer:cel(f)
    local img = source_image:clone()
    if cel then
        cel.image = img
        cel.position = Point(pos.x, pos.y)
    else
        sprite:newCel(layer, f, img, Point(pos.x, pos.y))
    end
end

_mcp_maybe_save(sprite, file)
print(string.format(
    "OK: propagated cel from layer '%s' frame %d to frames %d-%d",
    layer.name, source_frame, source_frame + 1, to_frame
))
