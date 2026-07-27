-- set_palette_color.lua：设置调色板指定索引的颜色
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略), index (0-based), color (#RRGGBB 格式)
-- 调用: aseprite -b --script set_palette_color.lua --script-param file=canvas.ase --script-param index=0 --script-param color=#FF0000
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
local index = tonumber(app.params["index"])
local color_hex = app.params["color"]

if not index or not color_hex then
    print("ERROR: index, color are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 获取精灵调色板
local pal = sprite.palettes[1]
if not pal then
    print("ERROR: no palette found")
    return
end

-- 检查索引是否越界
if index < 0 or index >= #pal then
    print("ERROR: index out of range (0-" .. (#pal - 1) .. ")")
    return
end

-- 解析十六进制颜色 #RRGGBB
local r, g, b = _mcp_hex_to_rgb(color_hex)

-- 设置调色板颜色（alpha 固定为 255）
pal:setColor(index, Color{r=r, g=g, b=b, a=255})

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: set palette color at index " .. index .. " to " .. color_hex)
