-- flip_canvas.lua：翻转画布（水平或垂直镜像）
-- 参数: file (CLI 模式必需，Live 模式可省略), direction ("horizontal" 或 "vertical")
-- 调用: aseprite -b --script flip_canvas.lua --script-param file=canvas.ase --script-param direction=horizontal
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
local direction = app.params["direction"]

-- 参数校验：direction 为必填，file 在 Live 模式下可省略
if not direction then
    print("ERROR: direction is required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite
if _G._mcp_get_sprite then
    sprite = _G._mcp_get_sprite(file)
else
    sprite = file and app.open(file) or app.activeSprite
end
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

-- 设置为活动精灵（执行 app.command 前必须设置）
app.activeSprite = sprite

-- 根据方向执行翻转命令
if direction == "horizontal" then
    app.command.Flip{ target="canvas", orientation="horizontal" }
elseif direction == "vertical" then
    app.command.Flip{ target="canvas", orientation="vertical" }
else
    print("ERROR: direction must be 'horizontal' or 'vertical'")
    return
end

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: flipped canvas " .. direction)
