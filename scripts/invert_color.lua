-- invert_color.lua：反转画布所有颜色（反色效果）
-- 参数: file
-- 调用: aseprite -b --script invert_color.lua --script-param file=canvas.ase

local file = app.params["file"]

-- 参数校验：file 为必填
if not file then
    print("ERROR: file is required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 执行颜色反转命令（对所有可见像素取反）
app.command.InvertColor()

sprite:saveAs(file)
print("OK: inverted colors")
