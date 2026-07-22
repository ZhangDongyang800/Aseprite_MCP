-- rotate_canvas.lua：旋转画布
-- 参数: file, angle (90, 180, 或 270)
-- 调用: aseprite -b --script rotate_canvas.lua --script-param file=canvas.ase --script-param angle=90

local file = app.params["file"]
local angle = tonumber(app.params["angle"])

-- 参数校验：file 和 angle 均为必填
if not file or not angle then
    print("ERROR: file and angle are required")
    return
end

-- 验证角度值：仅允许 90、180、270
if angle ~= 90 and angle ~= 180 and angle ~= 270 then
    print("ERROR: angle must be 90, 180, or 270")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 执行画布旋转命令
app.command.Rotate{ target="canvas", angle=angle }

sprite:saveAs(file)
print("OK: rotated canvas by " .. angle .. " degrees")
