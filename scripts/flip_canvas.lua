-- flip_canvas.lua：翻转画布（水平或垂直镜像）
-- 参数: file, direction ("horizontal" 或 "vertical")
-- 调用: aseprite -b --script flip_canvas.lua --script-param file=canvas.ase --script-param direction=horizontal

local file = app.params["file"]
local direction = app.params["direction"]

-- 参数校验：file 和 direction 均为必填
if not file or not direction then
    print("ERROR: file and direction are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 根据方向执行翻转命令
if direction == "horizontal" then
    app.command.Flip{ target="canvas", orientation="horizontal" }
elseif direction == "vertical" then
    app.command.Flip{ target="canvas", orientation="vertical" }
else
    print("ERROR: direction must be 'horizontal' or 'vertical'")
    return
end

sprite:saveAs(file)
print("OK: flipped canvas " .. direction)
