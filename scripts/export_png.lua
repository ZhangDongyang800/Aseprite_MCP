-- export_png.lua：导出画布为 PNG（支持缩放）
-- 参数: file (会话 .ase 路径), output (PNG 输出路径), scale (缩放倍数，默认 1)
-- 调用: aseprite -b --script export_png.lua --script-param file=canvas.ase --script-param output=preview.png --script-param scale=2

local file = app.params["file"]
local output = app.params["output"]
local scale = tonumber(app.params["scale"] or "1")

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 如果需要缩放，使用 sprite:resize
if scale > 1 then
    local new_width = sprite.width * scale
    local new_height = sprite.height * scale
    sprite:resize(new_width, new_height)
end

-- 导出为 PNG
sprite:saveCopyAs(output)
print("OK: exported PNG to " .. output .. " (scale=" .. scale .. ")")
