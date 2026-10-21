-- ops_draw.lua: drawing ops (v2 engine)
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

local function target_image(sprite, params)
    local layer = params.layer or 1
    local frame = params.frame or 1
    local image, err = _G._mcp_get_target_image(sprite, layer, frame)
    if not image then error(err) end
    return image
end

-- A Color object is converted for RGB/grayscale targets. Indexed images need an actual
-- palette index: Color:getIndex() is 0 for an RGB Color, so handing the object to
-- drawPixel would paint index 0 regardless of the requested hex. Map to the sprite palette.
local function paint_color(sprite, hex)
    local r, g, b = _mcp_hex_to_rgb(hex)
    if sprite.colorMode == ColorMode.INDEXED then
        local pal = sprite.palettes[1]
        if not pal or #pal == 0 then
            error("indexed sprite has no palette; call set_palette first")
        end
        local best, best_dist = 0, math.huge
        for i = 0, #pal - 1 do
            local c = pal:getColor(i)
            if c.alpha > 0 then
                local d = (c.red - r) ^ 2 + (c.green - g) ^ 2 + (c.blue - b) ^ 2
                if d < best_dist then
                    best, best_dist = i, d
                end
                if d == 0 then return i end
            end
        end
        return best
    end
    return Color{r = r, g = g, b = b, a = 255}
end

-- image:drawPixel() outside the cel is a silent no-op: the op reports ok and the pixel is
-- simply gone, so a typo'd coordinate costs a whole batch its feedback loop. Every op that
-- names coordinates checks them up front, the way _mcp_op_paint_grid already does.
local function inside(image, x, y)
    return x >= 0 and y >= 0 and x < image.width and y < image.height
end

function _G._mcp_op_clear_canvas(sprite, params)
    if params.layer == 0 then
        -- layer=0 clears the frame across every layer without creating missing cels.
        local frame = params.frame or 1
        local cleared = 0
        for li = 1, #sprite.layers do
            local cel = sprite.layers[li]:cel(frame)
            if cel then
                cel.image:clear()
                cleared = cleared + 1
            end
        end
        return {cleared = true, frame = frame, layers = cleared}
    end
    local image = target_image(sprite, params)
    image:clear()
    return {cleared = true}
end

function _G._mcp_op_draw_pixel(sprite, params)
    local image = target_image(sprite, params)
    if not inside(image, params.x, params.y) then
        error(("pixel %d,%d is outside the %dx%d canvas")
              :format(params.x, params.y, image.width, image.height))
    end
    image:drawPixel(params.x, params.y, paint_color(sprite, params.color))
    return {x = params.x, y = params.y}
end

function _G._mcp_op_draw_rect(sprite, params)
    local image = target_image(sprite, params)
    if not inside(image, params.x, params.y)
       or not inside(image, params.x + params.width - 1, params.y + params.height - 1) then
        error(("rect %d,%d %dx%d does not fit the %dx%d canvas")
              :format(params.x, params.y, params.width, params.height,
                      image.width, image.height))
    end
    _mcp_rect(image, params.x, params.y, params.width, params.height,
              paint_color(sprite, params.color), params.filled == true)
    return {x = params.x, y = params.y, width = params.width, height = params.height}
end

function _G._mcp_op_fill_region(sprite, params)
    local image = target_image(sprite, params)
    if not inside(image, params.x, params.y) then
        error(("fill seed %d,%d is outside the %dx%d canvas")
              :format(params.x, params.y, image.width, image.height))
    end
    _mcp_fill(image, params.x, params.y, paint_color(sprite, params.color), image.width, image.height)
    return {x = params.x, y = params.y}
end

function _G._mcp_op_draw_line(sprite, params)
    local image = target_image(sprite, params)
    if not inside(image, params.x1, params.y1)
       or not inside(image, params.x2, params.y2) then
        error(("line %d,%d -> %d,%d is outside the %dx%d canvas")
              :format(params.x1, params.y1, params.x2, params.y2,
                      image.width, image.height))
    end
    _mcp_line(image, params.x1, params.y1, params.x2, params.y2, paint_color(sprite, params.color))
    return {x1 = params.x1, y1 = params.y1, x2 = params.x2, y2 = params.y2}
end

function _G._mcp_op_draw_ellipse(sprite, params)
    local image = target_image(sprite, params)
    if params.cx - params.rx < 0 or params.cy - params.ry < 0
       or params.cx + params.rx >= image.width
       or params.cy + params.ry >= image.height then
        error(("ellipse center %d,%d radii %d,%d does not fit the %dx%d canvas")
              :format(params.cx, params.cy, params.rx, params.ry,
                      image.width, image.height))
    end
    _mcp_ellipse(image, params.cx, params.cy, params.rx, params.ry,
                 paint_color(sprite, params.color), params.filled == true)
    return {cx = params.cx, cy = params.cy, rx = params.rx, ry = params.ry}
end

function _G._mcp_op_paint_grid(sprite, params)
    -- The grid travels as a Lua data file, not JSON: this build's json.decode hands back a
    -- userdata that pairs()/# cannot walk, while dofile gives a real table.
    local ok, doc = pcall(dofile, params.path)
    if not ok then error("cannot load grid file: " .. tostring(doc)) end
    if type(doc) ~= "table" then
        error('grid file must return {palette = {b = "#rrggbb"}, rows = {"..."}}')
    end
    local palette, rows = doc.palette, doc.rows
    if type(palette) ~= "table" or type(rows) ~= "table" or #rows == 0 then
        error('grid file needs a "palette" table and a non-empty "rows" array')
    end

    local colors = {}
    for key, hex in pairs(palette) do
        if type(hex) ~= "string" then
            error("palette entry " .. tostring(key) .. " is not a hex string")
        end
        colors[key] = paint_color(sprite, hex)
    end

    local image = target_image(sprite, params)
    local ox, oy = params.x, params.y
    local painted, missing, outside = 0, {}, nil
    for y = 1, #rows do
        local row = rows[y]
        if type(row) ~= "string" then error("row " .. y .. " is not a string") end
        for x = 1, #row do
            local key = row:sub(x, x)
            if key ~= "." then
                local color = colors[key]
                if not color then
                    missing[key] = true
                else
                    local px, py = ox + x - 1, oy + y - 1
                    if px < 0 or py < 0 or px >= image.width or py >= image.height then
                        outside = outside or ("%d,%d on a %dx%d canvas"):format(px, py, image.width, image.height)
                    else
                        image:drawPixel(px, py, color)
                        painted = painted + 1
                    end
                end
            end
        end
    end

    -- Report only after scanning: the batch rolls the whole thing back on error anyway,
    -- and one message listing every bad code beats one per code.
    local keys = {}
    for key in pairs(missing) do keys[#keys + 1] = "'" .. key .. "'" end
    if #keys > 0 then
        table.sort(keys)
        error("grid uses codes missing from the palette: " .. table.concat(keys, " "))
    end
    if outside then error("grid paints outside the canvas: " .. outside) end
    return {painted = painted, width = #rows[1], height = #rows}
end
