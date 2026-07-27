-- replace_color.lua：将画布中的一种颜色替换为另一种颜色
-- 参数: file (CLI 模式必需，Live 模式可省略), from_color (#RRGGBB), to_color (#RRGGBB)
-- 调用: aseprite -b --script replace_color.lua --script-param file=canvas.ase --script-param from_color=#FF0000 --script-param to_color=#00FF00
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 修改实时反映在 Aseprite UI 上，不自动保存
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
local from_hex = app.params["from_color"]
local to_hex = app.params["to_color"]

-- 参数校验：from_color、to_color 为必填，file 在 Live 模式下可省略
if not from_hex or not to_hex then
    print("ERROR: from_color, to_color are required")
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

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 设置前景色为源颜色、背景色为目标颜色
app.fgColor = Color{ r=fr, g=fg, b=fb }
app.bgColor = Color{ r=tr, g=tg, b=tb }

-- 执行颜色替换命令：将前景色替换为背景色
app.command.ReplaceColor{ from=app.fgColor, to=app.bgColor }

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: replaced color " .. from_hex .. " with " .. to_hex)
