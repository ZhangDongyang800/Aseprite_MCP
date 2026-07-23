-- rotate_canvas.lua：旋转画布
-- 参数: file (CLI 模式必需，Live 模式可省略), angle (90, 180, 或 270)
-- 调用: aseprite -b --script rotate_canvas.lua --script-param file=canvas.ase --script-param angle=90
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
local angle = tonumber(app.params["angle"])

-- 参数校验：angle 为必填，file 在 Live 模式下可省略
if not angle then
    print("ERROR: angle is required")
    return
end

-- 验证角度值：仅允许 90、180、270
if angle ~= 90 and angle ~= 180 and angle ~= 270 then
    print("ERROR: angle must be 90, 180, or 270")
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

-- 执行画布旋转命令
app.command.Rotate{ target="canvas", angle=angle }

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: rotated canvas by " .. angle .. " degrees")
