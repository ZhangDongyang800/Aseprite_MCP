-- ops_structure.lua：文档结构 op（加帧、命名 tag）
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

function _G._mcp_op_add_frames(sprite, params)
    local count = params.count
    if count < 1 then error("count must be >= 1") end
    local last = #sprite.frames
    for _ = 1, count do
        sprite:newFrame(sprite.frames[#sprite.frames])
    end
    for i = last + 1, #sprite.frames do
        sprite.frames[i].duration = params.duration
        if not params.duplicate then
            -- newFrame duplicates the source cels, so a "blank" frame must be cleared
            for li = 1, #sprite.layers do
                local cel = sprite.layers[li]:cel(i)
                if cel then cel.image:clear() end
            end
        end
    end
    return {frames = #sprite.frames}
end

function _G._mcp_op_set_durations(sprite, params)
    local list = params.durations
    if #list > #sprite.frames then
        error(("%d durations for only %d frames"):format(#list, #sprite.frames))
    end
    for i, seconds in ipairs(list) do
        sprite.frames[i].duration = seconds
    end
    return {frames = #sprite.frames}
end

function _G._mcp_op_add_tag(sprite, params)
    local from, to = params.from_frame, params.to_frame
    if from < 1 or to > #sprite.frames or from > to then
        error(("tag range %d-%d is outside the 1..%d frame list")
              :format(from, to, #sprite.frames))
    end
    for ti = 1, #sprite.tags do
        if sprite.tags[ti].name == params.name then
            error("tag already exists: " .. params.name)
        end
    end
    local tag = sprite:newTag(from, to)
    if not tag then error("newTag returned nil") end
    tag.name = params.name
    -- this build ignores newTag's range arguments, so pin the endpoints explicitly
    tag.fromFrame = sprite.frames[from]
    tag.toFrame = sprite.frames[to]
    return {tags = #sprite.tags}
end
