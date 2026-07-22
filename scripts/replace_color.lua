-- replace_color.lua：将画布中的一种颜色替换为另一种颜色
-- 参数: file, from_color (#RRGGBB), to_color (#RRGGBB)
-- 调用: aseprite -b --script replace_color.lua --script-param file=canvas.ase --script-param from_color=#FF0000 --script-param to_color=#00FF00

local file = app.params["file"]
local from_hex = app.params["from_color"]
local to_hex = app.params["to_color"]

-- 参数校验：file、from_color、to_color 均为必填
if not file or not from_hex or not to_hex then
    print("ERROR: file, from_color, to_color are required")
    return
end

-- 解析源颜色（要被替换的颜色）的 RGB 分量
local fr = tonumber(from_hex:sub(2, 3), 16)
local fg = tonumber(from_hex:sub(4, 5), 16)
local fb = tonumber(from_hex:sub(6, 7), 16)

-- 解析目标颜色（替换后的颜色）的 RGB 分量
local tr = tonumber(to_hex:sub(2, 3), 16)
local tg = tonumber(to_hex:sub(4, 5), 16)
local tb = tonumber(to_hex:sub(6, 7), 16)

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 设置前景色为源颜色、背景色为目标颜色
app.fgColor = Color{ r=fr, g=fg, b=fb }
app.bgColor = Color{ r=tr, g=tg, b=tb }

-- 执行颜色替换命令：将前景色替换为背景色
app.command.ReplaceColor{ from=app.fgColor, to=app.bgColor }

sprite:saveAs(file)
print("OK: replaced color " .. from_hex .. " with " .. to_hex)
