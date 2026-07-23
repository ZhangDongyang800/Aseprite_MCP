-- draw_line.lua：画直线
-- 参数: file (CLI 模式必需，Live 模式可省略), x1, y1, x2, y2, color
-- 调用: aseprite -b --script draw_line.lua --script-param file=canvas.ase --script-param x1=0 --script-param y1=0 --script-param x2=15 --script-param y2=15 --script-param color=#FF0000
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
local x1 = tonumber(app.params["x1"])
local y1 = tonumber(app.params["y1"])
local x2 = tonumber(app.params["x2"])
local y2 = tonumber(app.params["y2"])
local color_hex = app.params["color"]

if not x1 or not y1 or not x2 or not y2 or not color_hex then
    print("ERROR: x1, y1, x2, y2, color are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite
if _G._mcp_get_sprite then
    sprite = _G._mcp_get_sprite(file)
else
    sprite = file and app.open(file) or app.activeSprite
end
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 解析颜色
local r = tonumber(color_hex:sub(2, 3), 16)
local g = tonumber(color_hex:sub(4, 5), 16)
local b = tonumber(color_hex:sub(6, 7), 16)
local pixel_color = app.pixelColor.rgba(r, g, b, 255)

-- 支持指定图层和帧（默认第1图层第1帧）
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

-- 使用 Bresenham 算法画线

local dx = math.abs(x2 - x1)
local dy = math.abs(y2 - y1)
local sx = x1 < x2 and 1 or -1
local sy = y1 < y2 and 1 or -1
local err = dx - dy

local cx, cy = x1, y1
while true do
    image:drawPixel(cx, cy, pixel_color)
    if cx == x2 and cy == y2 then break end
    local e2 = 2 * err
    if e2 > -dy then
        err = err - dy
        cx = cx + sx
    end
    if e2 < dx then
        err = err + dx
        cy = cy + sy
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: drew line from (" .. x1 .. "," .. y1 .. ") to (" .. x2 .. "," .. y2 .. ")")
