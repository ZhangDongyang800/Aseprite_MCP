-- crop_sprite.lua：裁剪精灵到指定矩形区域
-- 参数: file, x, y, width, height
-- 调用: aseprite -b --script crop_sprite.lua --script-param file=canvas.ase --script-param x=4 --script-param y=4 --script-param width=8 --script-param height=8

local file = app.params["file"]
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])
local w = tonumber(app.params["width"])
local h = tonumber(app.params["height"])

-- 参数校验：file、x、y、width、height 均为必填
if not file or not x or not y or not w or not h then
    print("ERROR: file, x, y, width, height are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 创建矩形选区并设置到精灵，然后执行裁剪命令
local sel = Selection(Rectangle(x, y, w, h))
sprite.selection = sel
app.command.CropSprite()

sprite:saveAs(file)
print("OK: cropped sprite to (" .. x .. "," .. y .. ") " .. w .. "x" .. h)
