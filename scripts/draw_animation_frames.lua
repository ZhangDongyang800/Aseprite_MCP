-- draw_animation_frames.lua：一次绘制多帧动画
-- 参数: file (CLI 模式必需，Live 模式可省略), grids (用 | 分隔每帧，帧内行用 / 分隔), colormap, mode (copy/blank), layer
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 修改实时反映在 Aseprite UI 上，不自动保存
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
local grids_str = app.params["grids"]
local colormap_str = app.params["colormap"]
local mode = app.params["mode"] or "copy"
local layer_idx = tonumber(app.params["layer"] or "1")

-- 参数校验：grids、colormap 为必填，file 在 Live 模式下可省略
if not grids_str or not colormap_str then
    print("ERROR: grids, colormap are required")
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
            local r, g, b = _mcp_hex_to_rgb(color)
            colormap[char] = app.pixelColor.rgba(r, g, b, 255)
        end
    end
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
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

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: drew " .. frames_drawn .. " frames")
