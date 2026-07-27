-- crop_sprite.lua：裁剪精灵到指定矩形区域
-- 参数: file (CLI 模式必需，Live 模式可省略), x, y, width, height
-- 调用: aseprite -b --script crop_sprite.lua --script-param file=canvas.ase --script-param x=4 --script-param y=4 --script-param width=8 --script-param height=8
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
local x = tonumber(app.params["x"])
local y = tonumber(app.params["y"])
local w = tonumber(app.params["width"])
local h = tonumber(app.params["height"])

-- 参数校验：x、y、width、height 为必填，file 在 Live 模式下可省略
if not x or not y or not w or not h then
    print("ERROR: x, y, width, height are required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 创建矩形选区并设置到精灵，然后执行裁剪命令
local sel = Selection(Rectangle(x, y, w, h))
sprite.selection = sel
app.command.CropSprite()

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: cropped sprite to (" .. x .. "," .. y .. ") " .. w .. "x" .. h)
