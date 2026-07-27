-- draw_rect.lua：画矩形（空心或实心）
-- 参数: file (CLI 模式必需，Live 模式可省略), x, y, width, height, color, filled (true/false，默认 false)
-- 调用: aseprite -b --script draw_rect.lua --script-param file=canvas.ase --script-param x=0 --script-param y=0 --script-param width=10 --script-param height=10 --script-param color=#FF0000 --script-param filled=true
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
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])
local w = tonumber(app.params["width"])
local h = tonumber(app.params["height"])
local color_hex = app.params["color"]
local filled = app.params["filled"] == "true"

if not x or not y or not w or not h or not color_hex then
    print("ERROR: x, y, width, height, color are required")
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

if filled then
    -- 实心矩形
    for py = y, y + h - 1 do
        for px = x, x + w - 1 do
            image:drawPixel(px, py, pixel_color)
        end
    end
else
    -- 空心矩形（只画边框）
    for px = x, x + w - 1 do
        image:drawPixel(px, y, pixel_color)             -- 上边
        image:drawPixel(px, y + h - 1, pixel_color)     -- 下边
    end
    for py = y, y + h - 1 do
        image:drawPixel(x, py, pixel_color)             -- 左边
        image:drawPixel(x + w - 1, py, pixel_color)     -- 右边
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: drew rect at (" .. x .. "," .. y .. ") " .. w .. "x" .. h .. " filled=" .. tostring(filled))
