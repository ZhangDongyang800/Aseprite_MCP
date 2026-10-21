-- ops_export.lua：把精灵写成交付物。永不修改文档，也不触碰 undo 快照。
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

-- Machine-readable document metadata travels with every export result. It is not a
-- separate JSON artifact; callers that need a manifest can persist this payload.
local function doc_metadata(sprite)
    local durations = {}
    for i, frame in ipairs(sprite.frames) do
        durations[i] = frame.duration  -- seconds, same unit as set_durations
    end
    local tags = {}
    for i, tag in ipairs(sprite.tags) do
        tags[i] = {name = tag.name,
                   from = tag.fromFrame.frameNumber,
                   to = tag.toFrame.frameNumber}
    end
    return {frame_count = #sprite.frames, durations = durations, tags = tags}
end

local function with_metadata(sprite, data)
    local meta = doc_metadata(sprite)
    for key, value in pairs(meta) do data[key] = value end
    return data
end

local function find_tag(sprite, name)
    for _, tag in ipairs(sprite.tags) do
        if tag.name == name then return tag end
    end
    return nil
end

local function frame_range(sprite, params)
    local from, to = 1, #sprite.frames
    if params.tag and params.tag ~= "" then
        local tag = find_tag(sprite, params.tag)
        if not tag then error("tag not found: " .. params.tag) end
        from = tag.fromFrame.frameNumber
        to = tag.toFrame.frameNumber
    end
    return from, to
end

local function clone_for_export(sprite)
    local clone = Sprite(sprite)
    if not clone then error("cannot clone sprite for export") end
    return clone
end

local function delete_frames_outside(clone, from, to)
    for i = #clone.frames, 1, -1 do
        if i < from or i > to then
            clone:deleteFrame(clone.frames[i])
        end
    end
end

local function resize_if_needed(sprite, scale)
    if scale and scale > 1 then
        sprite:resize(sprite.width * scale, sprite.height * scale)
    end
end

local function export_png(sprite, params)
    local frame = params.frame
    if not frame then
        if #sprite.frames == 1 then
            frame = 1
        else
            error("format='png' needs frame=... on a multi-frame sprite; "
                  .. "use format='frames' or 'sheet'")
        end
    end
    if frame < 1 or frame > #sprite.frames then
        error(("frame %d is outside 1..%d"):format(frame, #sprite.frames))
    end

    local clone = clone_for_export(sprite)
    delete_frames_outside(clone, frame, frame)
    clone:flatten()
    resize_if_needed(clone, params.scale)
    local w, h = clone.width, clone.height
    clone:saveCopyAs(params.output)
    clone:close()
    return with_metadata(sprite, {
        artifact_path = params.output, artifact_kind = "png",
        width = w, height = h, frames = 1, frame = frame,
    })
end

local function export_frames(sprite, params)
    local from, to = frame_range(sprite, params)
    local clone = clone_for_export(sprite)
    delete_frames_outside(clone, from, to)
    clone:flatten()
    resize_if_needed(clone, params.scale)
    local count = #clone.frames
    local w, h = clone.width, clone.height
    clone:saveCopyAs(params.output)
    clone:close()

    local paths = {}
    if count == 1 then
        paths[1] = params.output
    else
        -- Aseprite writes frame.png as frame1.png..frameN.png; the op reports
        -- those exact names so Python can verify every artifact exists.
        local base = params.output:sub(1, -5)
        local ext = params.output:sub(-4)
        for i = 1, count do paths[i] = base .. i .. ext end
    end
    return with_metadata(sprite, {
        artifact_paths = paths, artifact_kind = "png", artifact_role = "frame",
        width = w, height = h, frames = count, from_frame = from, to_frame = to,
    })
end

local function export_gif(sprite, params)
    local from, to = frame_range(sprite, params)
    local clone = clone_for_export(sprite)
    delete_frames_outside(clone, from, to)
    clone:flatten()
    resize_if_needed(clone, params.scale)
    local w, h, count = clone.width, clone.height, #clone.frames
    clone:saveCopyAs(params.output)
    clone:close()
    return with_metadata(sprite, {
        artifact_path = params.output, artifact_kind = "gif",
        width = w, height = h, frames = count, from_frame = from, to_frame = to,
    })
end

local function export_sheet(sprite, params)
    local from, to = frame_range(sprite, params)
    local clone = clone_for_export(sprite)
    delete_frames_outside(clone, from, to)
    clone:flatten()
    local n = #clone.frames
    if n == 0 then error("no frames to export") end

    local cols, rows
    if params.layout == "horizontal" then
        cols, rows = n, 1
    elseif params.layout == "vertical" then
        cols, rows = 1, n
    else
        cols = params.columns > 0 and math.min(params.columns, n)
               or math.max(1, math.ceil(math.sqrt(n)))
        rows = math.ceil(n / cols)
    end

    local w, h, gap = clone.width, clone.height, params.padding or 0
    local sheet_w = cols * w + math.max(0, cols - 1) * gap
    local sheet_h = rows * h + math.max(0, rows - 1) * gap
    local sheet = Image(sheet_w, sheet_h, clone.colorMode)
    sheet:clear()

    local layer = clone.layers[#clone.layers]
    if not layer then error("sprite has no layers") end
    for i = 1, n do
        local cel = layer:cel(clone.frames[i])
        if cel and cel.image then
            local x = ((i - 1) % cols) * (w + gap)
            local y = math.floor((i - 1) / cols) * (h + gap)
            sheet:drawImage(cel.image, Point(x + cel.position.x, y + cel.position.y))
        end
    end

    local out = Sprite(sheet_w, sheet_h, clone.colorMode)
    out.cels[1].image:drawImage(sheet)
    resize_if_needed(out, params.scale)
    local out_w, out_h = out.width, out.height
    out:saveCopyAs(params.output)
    out:close()
    clone:close()

    local scale = params.scale or 1
    local rects = {}
    for i = 1, n do
        rects[i] = {
            frame = from + i - 1,
            x = ((i - 1) % cols) * (w + gap) * scale,
            y = math.floor((i - 1) / cols) * (h + gap) * scale,
            width = w * scale,
            height = h * scale,
        }
    end
    return with_metadata(sprite, {
        artifact_path = params.output, artifact_kind = "png",
        width = out_w, height = out_h, frames = n,
        columns = cols, rows = rows,
        cell_width = w * scale, cell_height = h * scale,
        from_frame = from, to_frame = to, frame_rects = rects,
    })
end

function _G._mcp_op_export(sprite, params)
    if params.format == "png" then
        return export_png(sprite, params)
    elseif params.format == "frames" then
        return export_frames(sprite, params)
    elseif params.format == "gif" then
        return export_gif(sprite, params)
    elseif params.format == "sheet" then
        return export_sheet(sprite, params)
    end
    error("unknown export format: " .. tostring(params.format))
end
