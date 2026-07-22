-- resize_sprite.lua：调整精灵尺寸（缩放整个画布）
-- 参数: file, width, height (新尺寸，像素)
-- 调用: aseprite -b --script resize_sprite.lua --script-param file=canvas.ase --script-param width=32 --script-param height=32

local file = app.params["file"]
local width = tonumber(app.params["width"])
local height = tonumber(app.params["height"])

-- 参数校验：file、width、height 均为必填
if not file or not width or not height then
    print("ERROR: file, width, height are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 调整精灵尺寸（会按比例缩放所有像素内容）
sprite:resize(width, height)

sprite:saveAs(file)
print("OK: resized sprite to " .. width .. "x" .. height)
