-- export_png.lua：导出画布为 PNG（支持缩放）
-- 参数: file (CLI 模式必需，Live 模式可省略，会话 .ase 路径), output (PNG 输出路径，必填), scale (缩放倍数，默认 1)
-- 调用: aseprite -b --script export_png.lua --script-param file=canvas.ase --script-param output=preview.png --script-param scale=2
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 导出 PNG 副本到 output 路径
-- CLI 模式行为：
--   - 从 file 打开 sprite，导出 PNG 到 output

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local output = app.params["output"]
local scale = tonumber(app.params["scale"] or "1")

-- 参数校验：output 为必填（导出路径不可省略），file 在 Live 模式下可省略
if not output then
    print("ERROR: output is required")
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

-- 如果需要缩放，使用 sprite:resize
if scale > 1 then
    local new_width = sprite.width * scale
    local new_height = sprite.height * scale
    sprite:resize(new_width, new_height)
end

-- 导出为 PNG（saveCopyAs 导出副本，不改变源文件路径）
sprite:saveCopyAs(output)
print("OK: exported PNG to " .. output .. " (scale=" .. scale .. ")")
