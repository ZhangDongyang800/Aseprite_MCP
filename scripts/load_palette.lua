-- load_palette.lua：从文件加载调色板
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略), palette_file (调色板文件路径，支持 .gpl/.pal/.png)
-- 调用: aseprite -b --script load_palette.lua --script-param file=canvas.ase --script-param palette_file=pal.gpl
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
local palette_file = app.params["palette_file"]

if not palette_file then
    print("ERROR: palette_file is required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 从外部文件加载调色板到当前精灵
sprite:loadPalette(palette_file)

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: loaded palette from " .. palette_file)
