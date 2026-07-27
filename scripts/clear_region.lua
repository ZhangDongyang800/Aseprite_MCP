-- clear_region.lua：清除指定区域为透明
-- 参数: file (CLI 模式必需，Live 模式可省略), x, y, width, height
-- 调用: aseprite -b --script clear_region.lua --script-param file=canvas.ase --script-param x=0 --script-param y=0 --script-param width=5 --script-param height=5
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

if not x or not y or not w or not h then
    print("ERROR: x, y, width, height are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 透明像素颜色（alpha=0）
local transparent = app.pixelColor.rgba(0, 0, 0, 0)

-- 支持指定图层和帧（默认第1图层第1帧）
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local image, layer_err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then
    print("ERROR: " .. layer_err)
    return
end

-- 清除区域内的像素
for py = y, y + h - 1 do
    for px = x, x + w - 1 do
        if px >= 0 and px < sprite.width and py >= 0 and py < sprite.height then
            image:drawPixel(px, py, transparent)
        end
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: cleared region at (" .. x .. "," .. y .. ") " .. w .. "x" .. h)
