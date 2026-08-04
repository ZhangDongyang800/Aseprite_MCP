-- mcp_common.lua：Live/CLI 双模式兼容辅助模块
-- 通过 dofile 加载，在全局命名空间设置辅助函数。
--
-- 用法：在脚本开头加一行 dofile(...)
--   Live 模式：extension/main.lua 在 dofile 主脚本前先 dofile 本文件
--   CLI 模式：主脚本自己 dofile 本文件（路径通过 scripts_dir 推导）
--
-- 核心函数：
--   _mcp_get_sprite(file): Live 模式优先用 app.activeSprite，CLI 模式用 app.open(file)
--   _mcp_maybe_save(sprite, file): Live 模式跳过保存，CLI 模式保存
--   _mcp_is_live: 是否在 Live 模式（WebSocket 扩展环境）

-- 防止重复加载
if _G._mcp_common_loaded then
    return
end
_G._mcp_common_loaded = true

-- Live 模式标志：由 extension/main.lua 设置
-- 如果 _G._mcp_live_mode 未设置，说明在 CLI 模式下
_G._mcp_is_live = (_G._mcp_live_mode == true)

-- 获取 sprite：Live 模式优先用 app.activeSprite
-- 参数:
--   file: .ase 文件路径（CLI 模式必需，Live 模式可选）
-- 返回:
--   sprite 对象，或 nil + 错误信息
_G._mcp_get_sprite = function(file)
    -- Live 模式：优先用当前打开的 sprite
    if _G._mcp_is_live and app.activeSprite then
        return app.activeSprite
    end
    -- CLI 模式或 Live 模式但无 active sprite：从文件打开
    if file and file ~= "" then
        local sprite = app.open(file)
        if not sprite then
            return nil, "cannot open file: " .. file
        end
        return sprite
    end
    -- Live 模式但无 active sprite 且无 file 参数
    if _G._mcp_is_live then
        return nil, "no active sprite. Call create_sprite first."
    end
    return nil, "no file specified and not in live mode"
end

-- 保存 sprite：Live 模式跳过（UI 实时显示），CLI 模式保存
-- 参数:
--   sprite: sprite 对象
--   file: .ase 文件路径（CLI 模式必需）
_G._mcp_maybe_save = function(sprite, file)
    -- Live 模式下不自动保存：用户在 Aseprite 中能实时看到变化
    -- 如果需要保存到文件，用户可显式调用 save_sprite 工具
    if _G._mcp_is_live then
        return
    end
    -- CLI 模式：保存到文件
    if file and file ~= "" and sprite then
        sprite:saveAs(file)
    end
end

-- 获取或创建 sprite：用于 create_sprite 工具
-- Live 模式下如果已有 active sprite 且尺寸/模式匹配，则复用
-- 参数:
--   width, height, color_mode: 期望的尺寸和颜色模式
--   file: 输出文件路径（CLI 模式必需）
-- 返回:
--   sprite 对象, created (bool: true=新建, false=复用)
_G._mcp_get_or_create_sprite = function(width, height, color_mode, file)
    -- 映射颜色模式字符串到 ColorMode 常量
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

    -- Live 模式：检查是否可复用当前 sprite
    if _G._mcp_is_live and app.activeSprite then
        local s = app.activeSprite
        if s.width == width and s.height == height then
            -- 尺寸匹配，复用
            return s, false
        end
        -- 尺寸不匹配，关闭旧的，创建新的
        -- 注意：不自动关闭，让用户决定。直接新建会切换 active sprite
    end

    -- 创建新 sprite
    local sprite = Sprite(width, height, mode)
    if not sprite then
        return nil, false
    end

    -- CLI 模式：保存到文件
    if not _G._mcp_is_live and file and file ~= "" then
        sprite:saveAs(file)
    end

    return sprite, true
end

-- 解析十六进制颜色 #RRGGBB 为 r, g, b 值
-- 参数: hex (#RRGGBB 格式字符串，如 "#FF0000")
-- 返回: r, g, b 三个整数
_G._mcp_hex_to_rgb = function(hex)
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    return r, g, b
end

-- 获取指定图层/帧的 image，如果 cel 不存在则自动创建
-- 参数: sprite, layer_idx (1-based), frame_idx (1-based)
-- 返回: image 对象，或 nil + 错误信息
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
-- 共享绘制原语（供 draw_shape.lua、batch_edit.lua 等复用）
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

_G._mcp_fill = function(image, x, y, target_color, w, h)
    local src = image:getPixel(x, y)
    if src == target_color then return end
    local stack = {{x, y}}
    while #stack > 0 do
        local p = table.remove(stack)
        local px, py = p[1], p[2]
        if px >= 0 and px < w and py >= 0 and py < h then
            if image:getPixel(px, py) == src then
                image:drawPixel(px, py, target_color)
                table.insert(stack, {px+1, py})
                table.insert(stack, {px-1, py})
                table.insert(stack, {px, py+1})
                table.insert(stack, {px, py-1})
            end
        end
    end
end

_G._mcp_clear_rect = function(image, x, y, w, h)
    local t = Color{r=0,g=0,b=0,a=0}
    for py = y, y+h-1 do
        for px = x, x+w-1 do
            image:drawPixel(px, py, t)
        end
    end
end

-- 渐变填充（linear horizontal/vertical, radial）
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

-- Box blur 滤镜
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
-- 选区 Mask 文件 I/O（CLI 模式跨进程持久化选区）
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