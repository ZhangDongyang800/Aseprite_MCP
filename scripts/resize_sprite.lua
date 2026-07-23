-- resize_sprite.lua：调整精灵尺寸（缩放整个画布）
-- 参数: file (CLI 模式必需，Live 模式可省略), width, height (新尺寸，像素)
-- 调用: aseprite -b --script resize_sprite.lua --script-param file=canvas.ase --script-param width=32 --script-param height=32
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
local width = tonumber(app.params["width"])
local height = tonumber(app.params["height"])

-- 参数校验：width、height 为必填，file 在 Live 模式下可省略
if not width or not height then
    print("ERROR: width, height are required")
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

-- 调整精灵尺寸（会按比例缩放所有像素内容）
sprite:resize(width, height)

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: resized sprite to " .. width .. "x" .. height)
