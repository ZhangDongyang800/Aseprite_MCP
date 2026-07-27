-- draw_ellipse.lua：画椭圆（空心或实心）
-- 参数: file (CLI 模式必需，Live 模式可省略), cx (中心 x), cy (中心 y), rx (x 半径), ry (y 半径), color, filled
-- 调用: aseprite -b --script draw_ellipse.lua --script-param file=canvas.ase --script-param cx=8 --script-param cy=8 --script-param rx=5 --script-param ry=5 --script-param color=#FF0000 --script-param filled=true
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
local cx = tonumber(app.params["cx"])
local cy = tonumber(app.params["cy"])
local rx = tonumber(app.params["rx"])
local ry = tonumber(app.params["ry"])
local color_hex = app.params["color"]
local filled = app.params["filled"] == "true"

if not cx or not cy or not rx or not ry or not color_hex then
    print("ERROR: cx, cy, rx, ry, color are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 解析颜色
local r, g, b = _mcp_hex_to_rgb(color_hex)
local pixel_color = app.pixelColor.rgba(r, g, b, 255)

-- 支持指定图层和帧（默认第1图层第1帧）
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local image, layer_err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then
    print("ERROR: " .. layer_err)
    return
end

-- 使用中点椭圆算法
if filled then
    -- 实心椭圆：逐行扫描
    for py = cy - ry, cy + ry do
        local dy = py - cy
        local half_width = math.floor(rx * math.sqrt(1 - (dy * dy) / (ry * ry) + 0.5))
        for px = cx - half_width, cx + half_width do
            image:drawPixel(px, py, pixel_color)
        end
    end
else
    -- 空心椭圆：只画轮廓
    for py = cy - ry, cy + ry do
        local dy = py - cy
        local half_width = math.floor(rx * math.sqrt(1 - (dy * dy) / (ry * ry) + 0.5))
        if half_width >= 0 then
            image:drawPixel(cx - half_width, py, pixel_color)
            image:drawPixel(cx + half_width, py, pixel_color)
        end
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: drew ellipse at (" .. cx .. "," .. cy .. ") rx=" .. rx .. " ry=" .. ry .. " filled=" .. tostring(filled))
