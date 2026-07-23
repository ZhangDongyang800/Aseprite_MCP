-- create_tileset.lua：创建瓦片画布并设置网格为瓦片尺寸
-- 参数: file (CLI 模式必需，Live 模式可省略), tile_size, cols, rows
-- 行为: 创建 tile_size*cols × tile_size*rows 画布，设网格=tile_size
--
-- Live 模式行为：
--   - 创建新 sprite 并设为 activeSprite（无需 file 参数）
--   - 修改实时反映在 Aseprite UI 上，不自动保存
-- CLI 模式行为：
--   - 创建新 sprite 并保存到 file 路径

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local tile_size = tonumber(app.params["tile_size"])
local cols = tonumber(app.params["cols"])
local rows = tonumber(app.params["rows"])

-- 参数校验：tile_size、cols、rows 为必填，file 在 Live 模式下可省略
if not tile_size or not cols or not rows then
    print("ERROR: tile_size, cols, rows are required")
    return
end

local width = tile_size * cols
local height = tile_size * rows

-- 创建新精灵（RGB 模式）
local sprite = Sprite(width, height, ColorMode.RGB)
if not sprite then
    print("ERROR: failed to create sprite")
    return
end

-- 尝试设置网格大小为瓦片尺寸（docs §8.5）
-- app.gridBounds 是可读写属性
local grid_set = false
if app.gridBounds then
    app.gridBounds = Rectangle(0, 0, tile_size, tile_size)
    grid_set = true
end

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
if grid_set then
    print("OK: created tileset " .. width .. "x" .. height .. " grid=" .. tile_size .. " at " .. (file or "(live mode)"))
else
    -- 降级：网格未设置，提示瓦片尺寸
    print("OK: created tileset " .. width .. "x" .. height .. " (grid NOT set, tile_size=" .. tile_size .. ")")
end
