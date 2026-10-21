-- ops_session.lua: session lifecycle ops (v2 engine)
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

-- New document: Live always creates one, never reuses the active sprite (spec P0-7)
function _G._mcp_op_create_sprite(sprite, params)
    local mode = ColorMode.RGB
    if params.color_mode == "grayscale" then mode = ColorMode.GRAY
    elseif params.color_mode == "indexed" then mode = ColorMode.INDEXED end
    local created = Sprite(params.width, params.height, mode)
    if not created then error("cannot create sprite") end
    if params.file and params.file ~= "" then created:saveAs(params.file) end
    _G._mcp_created_sprite = created  -- handed to the generator's bootstrap stage
    local path = params.file
    if (not path or path == "") and created.filename then path = created.filename end
    return {width = created.width, height = created.height,
            color_mode = params.color_mode, canvas_path = path}
end

function _G._mcp_op_save_sprite(sprite, params)
    if params.path and params.path ~= "" then
        sprite:saveAs(params.path)
        return {saved = true, path = params.path}
    end
    local name = sprite.filename
    if not name or name == "" then
        error("no filename; pass path=... to save_sprite")
    end
    sprite:save()
    return {saved = true, path = sprite.filename}
end

function _G._mcp_op_open_sprite(sprite, params)
    local opened = app.open(params.path)
    if not opened then error("cannot open: " .. tostring(params.path)) end
    if params.file and params.file ~= "" then opened:saveAs(params.file) end
    _G._mcp_created_sprite = opened
    local path = params.file
    if (not path or path == "") and opened.filename then path = opened.filename end
    return {width = opened.width, height = opened.height,
            frames = #opened.frames, canvas_path = path}
end

function _G._mcp_op_add_layer(sprite, params)
    local layer = sprite:newLayer()
    layer.name = params.name
    layer.opacity = params.opacity
    return {layer = #sprite.layers, name = layer.name}
end

function _G._mcp_op_set_layer(sprite, params)
    local layer = sprite.layers[params.layer]
    if not layer then error("layer not found: " .. tostring(params.layer)) end
    if params.name ~= nil then layer.name = params.name end
    if params.opacity ~= nil then layer.opacity = params.opacity end
    if params.visible ~= nil then layer.isVisible = params.visible end
    return {layer = params.layer, name = layer.name,
            opacity = layer.opacity, visible = layer.isVisible}
end

function _G._mcp_op_delete_layer(sprite, params)
    if #sprite.layers <= 1 then
        error("cannot delete the last layer")
    end
    local layer = sprite.layers[params.layer]
    if not layer then error("layer not found: " .. tostring(params.layer)) end
    sprite:deleteLayer(layer)
    return {layers = #sprite.layers}
end

function _G._mcp_op_set_palette(sprite, params)
    local pal = Palette(#params.colors)
    for i, hex in ipairs(params.colors) do
        local r, g, b = _mcp_hex_to_rgb(hex)
        pal:setColor(i - 1, Color{r = r, g = g, b = b, a = 255})
    end
    sprite:setPalette(pal)
    return {colors = #params.colors, color_mode = tostring(sprite.colorMode)}
end
