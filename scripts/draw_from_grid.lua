-- draw_from_grid.lua：从文本网格一次性绘制整幅像素图
-- 这是最高效的绘制方式：用一个字符串表示整个像素布局，每个字符映射一种颜色
-- 参数: file, grid, colormap, offset_x (默认0), offset_y (默认0), layer, frame
-- grid 格式: 用 / 分隔行，每行是字符序列（每个字符代表一个像素）
-- colormap 格式: 用 , 分隔的 字符=颜色 对，如 R=#FF0000,W=#FFFFFF,.=transparent
-- 调用示例:
--   grid="RRR/WRW/RRR"
--   colormap="R=#FF0000,W=#FFFFFF,.=transparent"

local file = app.params["file"]
local grid_str = app.params["grid"]
local colormap_str = app.params["colormap"]
local offset_x = tonumber(app.params["offset_x"] or "0")
local offset_y = tonumber(app.params["offset_y"] or "0")

if not file or not grid_str or not colormap_str then
    print("ERROR: file, grid, colormap are required")
    return
end

-- 解析颜色映射表
local colormap = {}
for entry in colormap_str:gmatch("[^,]+") do
    -- 用 match 分离字符和颜色值：第一个字符是 key，= 后面是 value
    local char, color = entry:match("^(.)=(.+)$")
    if char then
        if color == "transparent" or color == "none" then
            -- 透明像素标记为 nil，绘制时跳过
            colormap[char] = nil
        else
            -- 解析十六进制颜色 #RRGGBB
            local r = tonumber(color:sub(2, 3), 16)
            local g = tonumber(color:sub(4, 5), 16)
            local b = tonumber(color:sub(6, 7), 16)
            colormap[char] = app.pixelColor.rgba(r, g, b, 255)
        end
    end
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 获取目标图层和帧
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local target_layer = sprite.layers[layer_idx]
if not target_layer then
    print("ERROR: layer not found: " .. layer_idx)
    return
end
local cel = target_layer:cel(frame_idx)
if not cel then
    cel = sprite:newCel(target_layer, frame_idx)
end
local image = cel.image

-- 解析网格并逐像素绘制
local row_idx = 0
local pixels_drawn = 0
for row in grid_str:gmatch("[^/]+") do
    local col_idx = 0
    -- 逐字符遍历当前行
    for char in row:gmatch(".") do
        local color = colormap[char]
        if color then
            image:drawPixel(offset_x + col_idx, offset_y + row_idx, color)
            pixels_drawn = pixels_drawn + 1
        end
        col_idx = col_idx + 1
    end
    row_idx = row_idx + 1
end

sprite:saveAs(file)
print("OK: drew grid " .. row_idx .. " rows, " .. pixels_drawn .. " pixels")
