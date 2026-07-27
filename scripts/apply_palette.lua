-- apply_palette.lua：整板替换调色板为指定颜色序列
-- 参数: file (CLI 模式必需，Live 模式可省略), colors (逗号分隔的 #RRGGBB 列表)
-- 行为: 调整调色板大小为 colors 数量，逐色写入（覆盖原调色板）
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
local colors_str = app.params["colors"]

-- 参数校验：colors 为必填，file 在 Live 模式下可省略
if not colors_str then
    print("ERROR: colors are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

local pal = sprite.palettes[1]
if not pal then
    print("ERROR: no palette found")
    return
end

-- 解析颜色列表
local colors = {}
for hex in colors_str:gmatch("[^,]+") do
    local r, g, b = _mcp_hex_to_rgb(hex)
    table.insert(colors, {r=r, g=g, b=b})
end

-- 调整调色板大小并写入（整板替换）
pal:resize(#colors)
for i, c in ipairs(colors) do
    pal:setColor(i - 1, Color{r=c.r, g=c.g, b=c.b, a=255})
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: applied palette with " .. #colors .. " colors")
