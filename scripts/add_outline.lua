-- add_outline.lua：自动为已有像素添加轮廓线
-- 找到所有非透明像素边缘的透明位置，用指定颜色填充，形成描边效果
-- 参数: file, color (#RRGGBB 格式), thickness (默认1), layer, frame
-- 调用示例:
--   aseprite -b --script add_outline.lua --script-param file=canvas.ase --script-param color=#000000 --script-param thickness=1

local file = app.params["file"]
local color_hex = app.params["color"]
local thickness = tonumber(app.params["thickness"] or "1")

if not file or not color_hex then
    print("ERROR: file, color are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 解析轮廓颜色
local r = tonumber(color_hex:sub(2, 3), 16)
local g = tonumber(color_hex:sub(4, 5), 16)
local b = tonumber(color_hex:sub(6, 7), 16)
local outline_color = app.pixelColor.rgba(r, g, b, 255)
local transparent = app.pixelColor.rgba(0, 0, 0, 0)  -- 完全透明

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
local w = sprite.width
local h = sprite.height

-- 第一步：收集所有需要描边的位置（非透明像素相邻的透明像素）
-- 使用集合避免重复添加
local outline_positions = {}
local function add_pos(x, y)
    -- 用 y * w + x 作为唯一键
    outline_positions[y * w + x] = true
end

-- 遍历所有像素，找到需要描边的位置
for py = 0, h - 1 do
    for px = 0, w - 1 do
        local pixel = image:getPixel(px, py)
        -- 只处理透明像素（alpha = 0）
        if app.pixelColor.rgbaA(pixel) == 0 then
            -- 检查四邻域是否有非透明像素
            local neighbors = {
                {px - 1, py}, {px + 1, py},
                {px, py - 1}, {px, py + 1},
            }
            for _, n in ipairs(neighbors) do
                local nx, ny = n[1], n[2]
                if nx >= 0 and nx < w and ny >= 0 and ny < h then
                    local npixel = image:getPixel(nx, ny)
                    if app.pixelColor.rgbaA(npixel) > 0 then
                        add_pos(px, py)
                        break
                    end
                end
            end
        end
    end
end

-- 第二步：如果 thickness > 1，向外扩展轮廓范围
for t = 2, thickness do
    local expansion = {}
    for key, _ in pairs(outline_positions) do
        local py = math.floor(key / w)
        local px = key % w
        -- 检查四邻域是否也是需要描边的位置，如果不是则添加
        local neighbors = {
            {px - 1, py}, {px + 1, py},
            {px, py - 1}, {px, py + 1},
        }
        for _, n in ipairs(neighbors) do
            local nx, ny = n[1], n[2]
            if nx >= 0 and nx < w and ny >= 0 and ny < h then
                local nkey = ny * w + nx
                if not outline_positions[nkey] then
                    local npixel = image:getPixel(nx, ny)
                    if app.pixelColor.rgbaA(npixel) == 0 then
                        expansion[nkey] = true
                    end
                end
            end
        end
    end
    -- 合并扩展结果
    for key, _ in pairs(expansion) do
        outline_positions[key] = true
    end
end

-- 第三步：绘制轮廓像素
local count = 0
for key, _ in pairs(outline_positions) do
    local py = math.floor(key / w)
    local px = key % w
    image:drawPixel(px, py, outline_color)
    count = count + 1
end

sprite:saveAs(file)
print("OK: added outline, " .. count .. " pixels outlined (thickness=" .. thickness .. ")")
