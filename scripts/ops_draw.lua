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
