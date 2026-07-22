-- draw_animation_frames.lua：一次绘制多帧动画
-- 参数: file, grids (用 | 分隔每帧，帧内行用 / 分隔), colormap, mode (copy/blank), layer
local file = app.params["file"]
local grids_str = app.params["grids"]
local colormap_str = app.params["colormap"]
local mode = app.params["mode"] or "copy"
local layer_idx = tonumber(app.params["layer"] or "1")

if not file or not grids_str or not colormap_str then
    print("ERROR: file, grids, colormap are required")
    return
end

-- 解析颜色映射表
local colormap = {}
for entry in colormap_str:gmatch("[^,]+") do
    local char, color = entry:match("^(.)=(.+)$")
    if char then
        if color == "transparent" or color == "none" then
            colormap[char] = nil
        else
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

local target_layer = sprite.layers[layer_idx]
if not target_layer then
    print("ERROR: layer not found: " .. layer_idx)
    return
end

-- 按 | 分割每帧的 grid
local frames_grid = {}
for frame_grid in grids_str:gmatch("[^|]+") do
    table.insert(frames_grid, frame_grid)
end

local frames_drawn = 0

-- 第 1 帧使用已有帧，第 2 帧起新建帧
local start_frame = 2
for fi = 1, #frames_grid do
    local frame_idx
    if fi == 1 then
        -- 第 1 帧使用现有第 1 帧
        frame_idx = 1
    else
        -- 新建帧
        local new_frame = sprite:newFrame(#sprite.frames + 1)
        frame_idx = new_frame.frameNumber
        -- copy 模式：复制上一帧的 cel
        if mode == "copy" then
            local prev_cel = target_layer:cel(frame_idx - 1)
            if prev_cel then
                local new_cel = sprite:newCel(target_layer, frame_idx, prev_cel.image, prev_cel.position)
            end
        end
    end

    -- 获取或创建当前帧的 cel
    local cel = target_layer:cel(frame_idx)
    if not cel then
        cel = sprite:newCel(target_layer, frame_idx)
    end
    local image = cel.image

    -- 解析本帧 grid 并绘制
    local row_idx = 0
    for row in frames_grid[fi]:gmatch("[^/]+") do
        local col_idx = 0
        for char in row:gmatch(".") do
            local color = colormap[char]
            if color then
                image:drawPixel(col_idx, row_idx, color)
            end
            col_idx = col_idx + 1
        end
        row_idx = row_idx + 1
    end
    frames_drawn = frames_drawn + 1
end

sprite:saveAs(file)
print("OK: drew " .. frames_drawn .. " frames")
