-- compare_frames.lua：帧间差异分析（动画一致性检查核心工具）
-- 参数: file (CLI 模式必需，Live 模式可省略), frame_a (1-based), frame_b (1-based)
-- 输出: JSON 字符串:
--   {"frame_a": a, "frame_b": b, "total_pixels": N, "changed_pixels": N, "changed_pct": x.x,
--    "bbox": {"x":..,"y":..,"width":..,"height":..}, "layers": [{"layer": i, "name": "...", "changed": N}]}
--
-- 用途: 让 AI 量化验证动画动作的帧间差异——"这个动作只该动这些像素"。
-- 若 changed_pct 过大说明帧间脱节（或画错了区域），过小说明没有动作。

if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end

local file = app.params["file"]
local frame_a = tonumber(app.params["frame_a"] or "1")
local frame_b = tonumber(app.params["frame_b"] or "2")

local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print('{"error": "no active sprite. Call create_sprite first, or provide file parameter."}')
    return
end

if frame_a < 1 or frame_a > #sprite.frames or frame_b < 1 or frame_b > #sprite.frames then
    print('{"error": "frame_a/frame_b out of range. frame count = ' .. #sprite.frames .. '"}')
    return
end

local w, h = sprite.width, sprite.height
local total = w * h

-- 取指定帧/图层的 cel image，缺失视为全透明
local function get_image(layer, frame_no)
    local cel = layer:cel(frame_no)
    if cel and cel.image then return cel.image end
    return nil
end

-- 像素是否相等（RGBA 全等）；nil image 视为透明
local function pixel_eq(img_a, img_b, x, y)
    local ca = img_a and img_a:getPixel(x, y) or 0
    local cb = img_b and img_b:getPixel(x, y) or 0
    if ca == 0 and cb == 0 then return true end
    if not img_a or not img_b then return false end
    return ca == cb
end

local changed = 0
local min_x, min_y, max_x, max_y = w, h, -1, -1
local layer_reports = {}

for li = 1, #sprite.layers do
    local layer = sprite.layers[li]
    local img_a = get_image(layer, frame_a)
    local img_b = get_image(layer, frame_b)
    local layer_changed = 0
    for y = 0, h - 1 do
        for x = 0, w - 1 do
            if not pixel_eq(img_a, img_b, x, y) then
                layer_changed = layer_changed + 1
                if x < min_x then min_x = x end
                if x > max_x then max_x = x end
                if y < min_y then min_y = y end
                if y > max_y then max_y = y end
            end
        end
    end
    changed = changed + layer_changed
    table.insert(layer_reports, string.format(
        '{"layer": %d, "name": "%s", "changed": %d}',
        li, layer.name, layer_changed
    ))
end

local changed_pct = total > 0 and changed / total * 100 or 0
local bbox_json
if max_x >= 0 then
    bbox_json = string.format(
        '{"x": %d, "y": %d, "width": %d, "height": %d}',
        min_x, min_y, max_x - min_x + 1, max_y - min_y + 1
    )
else
    bbox_json = 'null'
end

print(string.format(
    '{"frame_a": %d, "frame_b": %d, "total_pixels": %d, "changed_pixels": %d, ' ..
    '"changed_pct": %.2f, "bbox": %s, "layers": [%s]}',
    frame_a, frame_b, total, changed, changed_pct, bbox_json, table.concat(layer_reports, ", ")
))
