-- ops_draw.lua：绘制 op（v2 内核）
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

local function rgba(hex)
    local r, g, b = _mcp_hex_to_rgb(hex)
    return app.pixelColor.rgba(r, g, b, 255)
end

function _G._mcp_op_clear_canvas(sprite, params)
    local image = target_image(sprite, params)
    image:clear()
    return {cleared = true}
end

function _G._mcp_op_draw_pixel(sprite, params)
    local image = target_image(sprite, params)
    image:drawPixel(params.x, params.y, rgba(params.color))
    return {x = params.x, y = params.y}
end

function _G._mcp_op_draw_rect(sprite, params)
    local image = target_image(sprite, params)
    _mcp_rect(image, params.x, params.y, params.width, params.height,
              rgba(params.color), params.filled == true)
    return {x = params.x, y = params.y, width = params.width, height = params.height}
end

function _G._mcp_op_fill_region(sprite, params)
    local image = target_image(sprite, params)
    _mcp_fill(image, params.x, params.y, rgba(params.color), image.width, image.height)
    return {x = params.x, y = params.y}
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
        colors[key] = rgba(hex)
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
