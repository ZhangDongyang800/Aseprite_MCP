-- invert_color.lua：反转画布所有颜色（反色效果）
-- 参数: file (CLI 模式必需，Live 模式可省略)
-- 调用: aseprite -b --script invert_color.lua --script-param file=canvas.ase
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

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 执行颜色反转命令（对所有可见像素取反）
app.command.InvertColor()

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: inverted colors")
