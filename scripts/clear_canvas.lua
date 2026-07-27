-- clear_canvas.lua：清空整个画布
-- 参数: file (CLI 模式必需，Live 模式可省略)
-- 调用: aseprite -b --script clear_canvas.lua --script-param file=canvas.ase
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

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 透明像素颜色
local transparent = app.pixelColor.rgba(0, 0, 0, 0)

-- 支持指定图层和帧（默认第1图层第1帧）
local layer_idx = tonumber(app.params["layer"] or "1")
local frame_idx = tonumber(app.params["frame"] or "1")
local image, layer_err = _mcp_get_target_image(sprite, layer_idx, frame_idx)
if not image then
    print("ERROR: " .. layer_err)
    return
end

-- 清除所有像素
for y = 0, sprite.height - 1 do
    for x = 0, sprite.width - 1 do
        image:drawPixel(x, y, transparent)
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: cleared canvas")
