-- mirror_half.lua：镜像复制半幅画布到另一半（用于对称角色绘制）
-- 只需画一半，此脚本自动镜像复制到另一侧
-- 参数: file (CLI 模式必需，Live 模式可省略), axis (x 或 y), position (镜像轴位置), direction (left_to_right/right_to_left/top_to_bottom/bottom_to_top), layer, frame
-- axis="x" 时水平镜像（左右复制），axis="y" 时垂直镜像（上下复制）
-- position 是镜像轴所在的坐标位置
-- direction 指定从哪一侧复制到哪一侧
-- 调用示例:
--   aseprite -b --script mirror_half.lua --script-param file=canvas.ase --script-param axis=x --script-param position=8 --script-param direction=left_to_right
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
local axis = app.params["axis"] or "x"
local position = tonumber(app.params["position"] or "0")
local direction = app.params["direction"] or "left_to_right"

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local image, layer_err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then
    print("ERROR: " .. layer_err)
    return
end
local w = sprite.width
local h = sprite.height

local count = 0

if axis == "x" then
    -- 水平镜像（左右复制）
    if direction == "left_to_right" then
        -- 从左半部分复制到右半部分
        for py = 0, h - 1 do
            for px = 0, position - 1 do
                -- 镜像 x 坐标
                local mirror_x = 2 * position - px - 1
                if mirror_x >= 0 and mirror_x < w then
                    local pixel = image:getPixel(px, py)
                    -- 只复制非透明像素，避免覆盖右半部分已有的内容
                    if app.pixelColor.rgbaA(pixel) > 0 then
                        image:drawPixel(mirror_x, py, pixel)
                        count = count + 1
                    end
                end
            end
        end
    else
        -- right_to_left: 从右半部分复制到左半部分
        for py = 0, h - 1 do
            for px = position, w - 1 do
                local mirror_x = 2 * position - px - 1
                if mirror_x >= 0 and mirror_x < w then
                    local pixel = image:getPixel(px, py)
                    if app.pixelColor.rgbaA(pixel) > 0 then
                        image:drawPixel(mirror_x, py, pixel)
                        count = count + 1
                    end
                end
            end
        end
    end
elseif axis == "y" then
    -- 垂直镜像（上下复制）
    if direction == "top_to_bottom" then
        -- 从上半部分复制到下半部分
        for py = 0, position - 1 do
            for px = 0, w - 1 do
                local mirror_y = 2 * position - py - 1
                if mirror_y >= 0 and mirror_y < h then
                    local pixel = image:getPixel(px, py)
                    if app.pixelColor.rgbaA(pixel) > 0 then
                        image:drawPixel(px, mirror_y, pixel)
                        count = count + 1
                    end
                end
            end
        end
    else
        -- bottom_to_top: 从下半部分复制到上半部分
        for py = position, h - 1 do
            for px = 0, w - 1 do
                local mirror_y = 2 * position - py - 1
                if mirror_y >= 0 and mirror_y < h then
                    local pixel = image:getPixel(px, py)
                    if app.pixelColor.rgbaA(pixel) > 0 then
                        image:drawPixel(px, mirror_y, pixel)
                        count = count + 1
                    end
                end
            end
        end
    end
else
    print("ERROR: invalid axis, must be 'x' or 'y'")
    return
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: mirrored " .. count .. " pixels (axis=" .. axis .. ", position=" .. position .. ", direction=" .. direction .. ")")
