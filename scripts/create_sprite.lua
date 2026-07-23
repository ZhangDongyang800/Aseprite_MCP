-- create_sprite.lua：创建新精灵或复用当前精灵（Live 模式）
-- 参数: width, height, color_mode (rgb/grayscale/indexed), file (输出路径，CLI 模式必需)
-- 调用: aseprite -b --script create_sprite.lua --script-param width=16 --script-param height=16 --script-param color_mode=rgb --script-param file=canvas.ase
--
-- Live 模式行为：
--   - 如果已有 active sprite 且尺寸匹配，直接复用，不创建新文件
--   - 如果尺寸不匹配，创建新 sprite（会切换 active sprite）
-- CLI 模式行为：
--   - 始终创建新 sprite 并保存到 file 路径

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local width = tonumber(app.params["width"])
local height = tonumber(app.params["height"])
local color_mode = app.params["color_mode"] or "rgb"
local file = app.params["file"]

if not width or not height then
    print("ERROR: width and height are required")
    return
end

-- 使用公共模块创建或复用 sprite
local sprite, created
if _G._mcp_get_or_create_sprite then
    sprite, created = _G._mcp_get_or_create_sprite(width, height, color_mode, file)
else
    -- fallback：直接创建
    local mode = ColorMode.RGB
    if color_mode == "grayscale" then mode = ColorMode.GRAYSCALE
    elseif color_mode == "indexed" then mode = ColorMode.INDEXED end
    sprite = Sprite(width, height, mode)
    created = true
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end

if not sprite then
    print("ERROR: failed to create sprite")
    return
end

if created then
    print("OK: created sprite " .. width .. "x" .. height .. " " .. color_mode .. " at " .. (file or "(live mode)"))
else
    print("OK: reused active sprite " .. sprite.width .. "x" .. sprite.height .. " (live mode)")
end
