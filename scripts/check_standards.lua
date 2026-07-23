-- check_standards.lua：遍历画布返回规范检查报告（JSON）
-- 参数: file
-- 检查: size(尺寸), color_count(颜色数), palette_consistency, timing(帧时长), pixel_art(半透明/孤立像素)
local file = app.params["file"]
if not file then
    print('{"error": "file is required"}')
    return
end

local sprite = app.open(file)
if not sprite then
    print('{"error": "cannot open file"}')
    return
end

local w = sprite.width
local h = sprite.height

-- 1. 尺寸检查（docs §2.1：尺寸应为 8 的倍数）
local size_pass = (w % 8 == 0 and h % 8 == 0)
local size_detail = w .. "x" .. h
local size_suggestion = "dimensions should be multiple of 8 (docs §2.1)"

-- 2. 颜色数与半透明/孤立像素检查
local color_set = {}
local color_count = 0
local semi_transparent = 0
local pixel_positions = {}

local layer = sprite.layers[1]
local cel = layer:cel(1)
local has_image = cel and cel.image
if has_image then
    local img = cel.image
    -- 遍历像素：统计颜色数、半透明像素、记录位置用于孤立像素检测
    for it in img:pixels() do
        local pc = it()
        local a = app.pixelColor.rgbaA(pc)
        if a > 0 then
            -- 半透明像素计数（docs §5.1 禁止半透明）
            if a < 255 then
                semi_transparent = semi_transparent + 1
            end
            local r = app.pixelColor.rgbaR(pc)
            local g = app.pixelColor.rgbaG(pc)
            local b = app.pixelColor.rgbaB(pc)
            -- 用 rgb 组合作为去重 key
            local key = r * 65536 + g * 256 + b
            if not color_set[key] then
                color_set[key] = true
                color_count = color_count + 1
            end
            -- 记录像素位置用于孤立像素检测
            table.insert(pixel_positions, {x=it.x, y=it.y, c=key})
        end
    end
end

-- 孤立像素检测（被异色包围，可能为 jaggies/噪点，docs §5.2）
local pixel_map = {}
for _, p in ipairs(pixel_positions) do
    pixel_map[p.x .. "," .. p.y] = p.c
end
local isolated = 0
for _, p in ipairs(pixel_positions) do
    -- 检查四邻像素颜色
    local neighbors = {
        pixel_map[(p.x-1) .. "," .. p.y],
        pixel_map[(p.x+1) .. "," .. p.y],
        pixel_map[p.x .. "," .. (p.y-1)],
        pixel_map[p.x .. "," .. (p.y+1)],
    }
    local same_count = 0
    local has_neighbor = 0
    for _, nc in ipairs(neighbors) do
        if nc then
            has_neighbor = has_neighbor + 1
            if nc == p.c then same_count = same_count + 1 end
        end
    end
    -- 四邻全异色视为孤立
    if has_neighbor == 4 and same_count == 0 then
        isolated = isolated + 1
    end
end

-- 3. 帧时长检查（docs §7.2：不同动作用不同时长）
local frame_total = #sprite.frames
local timing_pass = true
local timing_detail = "single frame"
if frame_total > 1 then
    local first_dur = sprite.frames[1].duration
    local all_same = true
    for i = 2, frame_total do
        if sprite.frames[i].duration ~= first_dur then
            all_same = false
            break
        end
    end
    -- 多帧但全相同时长视为违规
    timing_pass = not all_same
    timing_detail = all_same and "all frames same duration (violates docs §7.2)" or "varied durations"
end

-- 4. 构造 JSON 报告（单行 JSON 输出）
local function check_item(pass, detail, suggestion)
    return string.format('{"pass": %s, "detail": "%s", "suggestion": "%s"}',
        pass and "true" or "false", detail, suggestion)
end

local report = string.format(
    '{"success": true, "checks": {"size": %s, "color_count": %s, "timing": %s, "pixel_art": {"semi_transparent": %s, "isolated_pixels": %s, "visual_review": "%s"}}, "stats": {"width": %d, "height": %d, "color_count": %d, "frames": %d}}',
    check_item(size_pass, size_detail, size_suggestion),
    check_item(color_count >= 4 and color_count <= 32, color_count .. " colors", "use 4-32 colors (docs §4.1)"),
    check_item(timing_pass, timing_detail, "vary duration per action (docs §7.2)"),
    check_item(semi_transparent == 0, semi_transparent .. " semi-transparent pixels", "no semi-transparent pixels (docs §5.1)"),
    check_item(isolated == 0, isolated .. " isolated pixels", "possible jaggies/noise (docs §5.2)"),
    "review jaggies/pillow shading via export_silhouette + get_canvas_preview (docs §5.2/§5.4)",
    w, h, color_count, frame_total
)

print(report)
