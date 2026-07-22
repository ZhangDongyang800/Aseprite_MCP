-- create_tileset.lua：创建瓦片画布并设置网格为瓦片尺寸
-- 参数: file, tile_size, cols, rows
-- 行为: 创建 tile_size*cols × tile_size*rows 画布，设网格=tile_size
local file = app.params["file"]
local tile_size = tonumber(app.params["tile_size"])
local cols = tonumber(app.params["cols"])
local rows = tonumber(app.params["rows"])

if not file or not tile_size or not cols or not rows then
    print("ERROR: file, tile_size, cols, rows are required")
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

sprite:saveAs(file)
if grid_set then
    print("OK: created tileset " .. width .. "x" .. height .. " grid=" .. tile_size .. " at " .. file)
else
    -- 降级：网格未设置，提示瓦片尺寸
    print("OK: created tileset " .. width .. "x" .. height .. " (grid NOT set, tile_size=" .. tile_size .. ")")
end
