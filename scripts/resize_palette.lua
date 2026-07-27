-- resize_palette.lua：调整调色板大小（颜色数量）
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略), size (新的颜色数量)
-- 调用: aseprite -b --script resize_palette.lua --script-param file=canvas.ase --script-param size=32
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
local size = tonumber(app.params["size"])

if not size then
    print("ERROR: size is required")
    return
end

-- 参数校验：size 必须为正整数
if size < 0 then
    print("ERROR: size must be non-negative")
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

-- 调整调色板大小
pal:resize(size)

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: resized palette to " .. size .. " colors")
