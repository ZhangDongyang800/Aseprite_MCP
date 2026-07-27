-- fill_region.lua：油漆桶填充连通区域
-- 参数: file (CLI 模式必需，Live 模式可省略), x, y, color
-- 使用洪水填充算法填充与 (x,y) 相同颜色的连通区域
-- 调用: aseprite -b --script fill_region.lua --script-param file=canvas.ase --script-param x=5 --script-param y=5 --script-param color=#FF0000
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
local color_hex = app.params["color"]

if not x or not y or not color_hex then
    print("ERROR: x, y, color are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 解析目标颜色
local r, g, b = _mcp_hex_to_rgb(color_hex)
local fill_color = app.pixelColor.rgba(r, g, b, 255)

-- 支持指定图层和帧（默认第1图层第1帧）
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local image, layer_err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then
    print("ERROR: " .. layer_err)
    return
end
local w = sprite.width
local h = sprite.height

-- 获取目标位置当前颜色
local target_color = image:getPixel(x, y)

-- 如果目标颜色与填充颜色相同，不操作
if target_color == fill_color then
    print("OK: target color matches fill color, no change")
    return
end

-- 洪水填充（使用栈避免递归溢出）
local stack = {{x, y}}
while #stack > 0 do
    local point = table.remove(stack)
    local px, py = point[1], point[2]

    -- 边界检查
    if px >= 0 and px < w and py >= 0 and py < h then
        if image:getPixel(px, py) == target_color then
            image:drawPixel(px, py, fill_color)
            table.insert(stack, {px + 1, py})
            table.insert(stack, {px - 1, py})
            table.insert(stack, {px, py + 1})
            table.insert(stack, {px, py - 1})
        end
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: filled region from (" .. x .. "," .. y .. ")")
