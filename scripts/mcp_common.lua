-- mcp_common.lua: helper module shared by Live and CLI mode
-- Loaded with dofile; installs its helpers in the global namespace.
--
-- Usage: add one dofile(...) line at the top of a script
--   Live mode: extension/main.lua dofiles this file before the main script
--   CLI mode: the main script dofiles it itself (path derived from scripts_dir)
--
-- Core functions:
--   _mcp_get_sprite(file): Live prefers app.activeSprite, CLI uses app.open(file)
--   _mcp_maybe_save(sprite, file): skipped in Live mode, saves in CLI mode
--   _mcp_is_live: whether we are in Live mode (inside the WebSocket extension)

-- Guard against double loading
if _G._mcp_common_loaded then
    return
end
_G._mcp_common_loaded = true

-- Live-mode flag: set by extension/main.lua
-- If _G._mcp_live_mode is unset, we are running under the CLI
_G._mcp_is_live = (_G._mcp_live_mode == true)

-- Get the sprite: Live mode prefers app.activeSprite
-- Params:
--   file: .ase path (required in CLI mode, optional in Live mode)
-- Returns:
--   a sprite, or nil + an error message
_G._mcp_get_sprite = function(file)
    -- Live mode: prefer the sprite that is already open
    if _G._mcp_is_live and app.activeSprite then
        return app.activeSprite
    end
    -- CLI mode, or Live mode without an active sprite: open from the file
    if file and file ~= "" then
        local sprite = app.open(file)
        if not sprite then
            return nil, "cannot open file: " .. file
        end
        return sprite
    end
    -- Live mode, no active sprite and no file argument
    if _G._mcp_is_live then
        return nil, "no active sprite. Call create_sprite first."
    end
    return nil, "no file specified and not in live mode"
end

-- Save the sprite: skipped in Live mode (the UI shows changes live), saves in CLI mode
-- Params:
--   sprite: the sprite object
--   file: .ase path (required in CLI mode)
_G._mcp_maybe_save = function(sprite, file)
    -- No autosave in Live mode: the user watches every change in Aseprite as it happens
    -- To write a file, the user calls the save_sprite tool explicitly
    if _G._mcp_is_live then
        return
    end
    -- CLI mode: write the file
    if file and file ~= "" and sprite then
        sprite:saveAs(file)
    end
end

-- Get or create a sprite: used by the create_sprite tool
-- In Live mode, reuse the active sprite when its size/mode matches
-- Params:
--   width, height, color_mode: the size and color mode we want
--   file: output path (required in CLI mode)
-- Returns:
--   the sprite, created (bool: true = new, false = reused)
_G._mcp_get_or_create_sprite = function(width, height, color_mode, file)
    -- Map the color-mode string onto a ColorMode constant
    local mode
    if color_mode == "rgb" then
        mode = ColorMode.RGB
    elseif color_mode == "grayscale" then
        mode = ColorMode.GRAYSCALE
    elseif color_mode == "indexed" then
        mode = ColorMode.INDEXED
    else
        mode = ColorMode.RGB
    end

    -- Live mode: see whether the current sprite can be reused
    if _G._mcp_is_live and app.activeSprite then
        local s = app.activeSprite
        if s.width == width and s.height == height then
            -- Size matches, reuse it
            return s, false
        end
        -- Size differs: close the old one and create a new one
        -- Note: left open for the user to decide; creating a sprite switches the active one
    end

    -- Create a new sprite
    local sprite = Sprite(width, height, mode)
    if not sprite then
        return nil, false
    end

    -- CLI mode: write the file
    if not _G._mcp_is_live and file and file ~= "" then
        sprite:saveAs(file)
    end

    return sprite, true
end

-- Parse a #RRGGBB hex color into r, g, b
-- Params: hex (#RRGGBB string, e.g. "#FF0000")
-- Returns: three integers, r, g, b
_G._mcp_hex_to_rgb = function(hex)
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    return r, g, b
end

-- Get the image of a layer/frame; a missing cel is created on demand
-- Params: sprite, layer_idx (1-based), frame_idx (1-based)
-- Returns: an image, or nil + an error message
_G._mcp_get_target_image = function(sprite, layer_idx, frame_idx)
    local target_layer = sprite.layers[layer_idx]
    if not target_layer then
        return nil, "layer not found: " .. tostring(layer_idx)
    end
    local cel = target_layer:cel(frame_idx)
    if not cel then
        cel = sprite:newCel(target_layer, frame_idx)
    end
    return cel.image
end

-- ============================================================
-- Shared drawing primitives (reused by draw_shape.lua, batch_edit.lua, ...)
-- ============================================================

_G._mcp_pixel = function(image, x, y, color)
    image:drawPixel(x, y, color)
end

_G._mcp_line = function(image, x1, y1, x2, y2, color)
    local dx = math.abs(x2 - x1)
    local dy = math.abs(y2 - y1)
    local sx = x1 < x2 and 1 or -1
    local sy = y1 < y2 and 1 or -1
    local err = dx - dy
    while true do
        image:drawPixel(x1, y1, color)
        if x1 == x2 and y1 == y2 then break end
        local e2 = 2 * err
        if e2 > -dy then err = err - dy; x1 = x1 + sx end
        if e2 <  dx then err = err + dx; y1 = y1 + sy end
    end
end

_G._mcp_rect = function(image, x, y, w, h, color, filled)
    if filled then
        for py = y, y + h - 1 do
            for px = x, x + w - 1 do
                image:drawPixel(px, py, color)
            end
        end
    else
        _G._mcp_line(image, x, y, x + w - 1, y, color)
        _G._mcp_line(image, x, y + h - 1, x + w - 1, y + h - 1, color)
        _G._mcp_line(image, x, y, x, y + h - 1, color)
        _G._mcp_line(image, x + w - 1, y, x + w - 1, y + h - 1, color)
    end
end

_G._mcp_ellipse = function(image, cx, cy, rx, ry, color, filled)
    local function draw_points(ix, iy)
        image:drawPixel(cx + ix, cy + iy, color)
        image:drawPixel(cx - ix, cy + iy, color)
        image:drawPixel(cx + ix, cy - iy, color)
        image:drawPixel(cx - ix, cy - iy, color)
    end
    if filled then
        for py = cy - ry, cy + ry do
            for px = cx - rx, cx + rx do
                local dx2, dy2 = (px - cx)^2, (py - cy)^2
                if rx > 0 and ry > 0 and (dx2/(rx*rx) + dy2/(ry*ry)) <= 1 then
                    image:drawPixel(px, py, color)
                end
            end
        end
    else
        local x, y = 0, ry
        local d1 = ry*ry - rx*rx*ry + 0.25*rx*rx
        local dx, dy = 2*ry*ry*x, 2*rx*rx*y
        while dx < dy do
            draw_points(x, y)
            if d1 < 0 then x = x+1; dx = dx+2*ry*ry; d1 = d1+dx+ry*ry
            else x = x+1; y = y-1; dx = dx+2*ry*ry; dy = dy-2*rx*rx; d1 = d1+dx-dy+ry*ry end
        end
        local d2 = ry*ry*(x+0.5)^2 + rx*rx*(y-1)^2 - rx*rx*ry*ry
        while y >= 0 do
            draw_points(x, y)
            if d2 > 0 then y = y-1; dy = dy-2*rx*rx; d2 = d2+rx*rx-dy
            else x = x+1; y = y-1; dx = dx+2*ry*ry; dy = dy-2*rx*rx; d2 = d2+dx-dy+rx*rx end
        end
    end
end

-- Flood fill (scanline algorithm)
-- A per-pixel 4-neighbour DFS news a table per pixel and pushes it up to 4 times: a 4096² canvas
-- is 60M+ allocations, a guaranteed subprocess timeout. The scanline eats a whole row at a time
-- and touches each pixel with exactly one get and one put.
_G._mcp_fill = function(image, x, y, target_color, w, h)
    if x < 0 or y < 0 or x >= w or y >= h then return 0 end
    local src = image:getPixel(x, y)
    if src == target_color then return 0 end
    local filled = 0
    local seeds = {{x, y}}
    while #seeds > 0 do
        local seed = table.remove(seeds)
        local sx, sy = seed[1], seed[2]
        if sy >= 0 and sy < h and sx >= 0 and sx < w and image:getPixel(sx, sy) == src then
            -- Expand left and right into a full span
            local left, right = sx, sx
            while left - 1 >= 0 and image:getPixel(left - 1, sy) == src do left = left - 1 end
            while right + 1 < w and image:getPixel(right + 1, sy) == src do right = right + 1 end
            for px = left, right do
                image:drawPixel(px, sy, target_color)
            end
            filled = filled + (right - left + 1)
            -- src pixels in the rows above/below seed them (one push per span)
            for _, ny in ipairs({sy - 1, sy + 1}) do
                if ny >= 0 and ny < h then
                    local pending = false
                    for px = left, right do
                        if image:getPixel(px, ny) == src then
                            if not pending then
                                seeds[#seeds + 1] = {px, ny}
                                pending = true
                            end
                        else
                            pending = false
                        end
                    end
                end
            end
        end
    end
    return filled
end

_G._mcp_clear_rect = function(image, x, y, w, h)
    local t = Color{r=0,g=0,b=0,a=0}
    for py = y, y+h-1 do
        for px = x, x+w-1 do
            image:drawPixel(px, py, t)
        end
    end
end

-- Gradient fill (linear horizontal/vertical, radial)
_G._mcp_gradient = function(image, x, y, w, h, from_c, to_c, mode, direction)
    for py = y, y+h-1 do
        for px = x, x+w-1 do
            local t
            if mode == "linear" then
                if direction == "horizontal" then
                    t = w > 1 and (px-x)/(w-1) or 0
                else
                    t = h > 1 and (py-y)/(h-1) or 0
                end
            else
                local cx, cy2 = x+w/2, y+h/2
                local max_r = math.sqrt(w*w+h*h)/2
                t = max_r > 0 and math.sqrt((px-cx)^2+(py-cy2)^2)/max_r or 0
            end
            t = math.max(0, math.min(1, t))
            image:drawPixel(px, py, Color{
                r=from_c.red+t*(to_c.red-from_c.red),
                g=from_c.green+t*(to_c.green-from_c.green),
                b=from_c.blue+t*(to_c.blue-from_c.blue),
                a=from_c.alpha+t*(to_c.alpha-from_c.alpha),
            })
        end
    end
end

-- Box blur filter
_G._mcp_blur = function(image, radius, strength)
    local w, h = image.width, image.height
    local orig = Image(image)
    strength = strength or 1
    for py = 0, h-1 do
        for px = 0, w-1 do
            local r, g, b, a, n = 0,0,0,0,0
            for dy = -radius, radius do
                for dx = -radius, radius do
                    local nx, ny = px+dx, py+dy
                    if nx>=0 and nx<w and ny>=0 and ny<h then
                        local c = orig:getPixel(nx, ny)
                        r,g,b,a = r+c.red, g+c.green, b+c.blue, a+c.alpha
                        n = n+1
                    end
                end
            end
            local oc = orig:getPixel(px, py)
            local s = math.min(1, strength)
            image:drawPixel(px, py, Color{
                r=math.max(0,math.min(255,oc.red+s*(r/n-oc.red))),
                g=math.max(0,math.min(255,oc.green+s*(g/n-oc.green))),
                b=math.max(0,math.min(255,oc.blue+s*(b/n-oc.blue))),
                a=math.max(0,math.min(255,oc.alpha+s*(a/n-oc.alpha))),
            })
        end
    end
end

-- ============================================================
-- Selection mask file I/O (keeps the selection across processes in CLI mode)
-- ============================================================

_G._mcp_save_selection = function(sprite, path)
    if not sprite or not path then return end
    local sel = sprite.selection
    if sel.isEmpty then
        local f = io.open(path, "w")
        if f then f:write("0 0\n"); f:close() end
        return
    end
    local b = sel.bounds
    local f = io.open(path, "w")
    if not f then return end
    f:write(b.width .. " " .. b.height .. "\n")
    for py = b.y, b.y+b.height-1 do
        local spans = {}
        local in_span, ss = false, 0
        for px = b.x, b.x+b.width-1 do
            if sel:contains(Point(px, py)) then
                if not in_span then ss = px-b.x; in_span = true end
            else
                if in_span then table.insert(spans, ss.."-"..(px-b.x-1)); in_span = false end
            end
        end
        if in_span then table.insert(spans, ss.."-"..(b.width-1)) end
        f:write(table.concat(spans, ",") .. "\n")
    end
    f:close()
end

_G._mcp_load_selection = function(sprite, path)
    local f = io.open(path, "r")
    if not f then return function(x,y) return false end end
    local hdr = f:read("*line")
    if not hdr then f:close(); return function(x,y) return false end end
    local sw, sh = hdr:match("(%d+) (%d+)")
    if not sw then f:close(); return function(x,y) return false end end
    sw, sh = tonumber(sw), tonumber(sh)
    if sw == 0 or sh == 0 then f:close(); return function(x,y) return false end end
    local rows = {}
    for i = 1, sh do
        local line = f:read("*line")
        if line and line ~= "" then
            local spans = {}
            for seg in line:gmatch("[^,]+") do
                local s, e = seg:match("(%d+)-(%d+)")
                if s and e then table.insert(spans, {tonumber(s), tonumber(e)}) end
            end
            rows[i] = spans
        end
    end
    f:close()
    return function(x, y)
        local row = rows[y+1]
        if not row then return false end
        for _, sp in ipairs(row) do
            if x >= sp[1] and x <= sp[2] then return true end
        end
        return false
    end
end