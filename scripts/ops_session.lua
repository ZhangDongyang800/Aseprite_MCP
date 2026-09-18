-- ops_session.lua：会话生命周期 op（v2 内核）
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

-- 新建文档：Live 始终新建，不复用活动 sprite（spec P0-7）
function _G._mcp_op_create_sprite(sprite, params)
    local mode = ColorMode.RGB
    if params.color_mode == "grayscale" then mode = ColorMode.GRAY
    elseif params.color_mode == "indexed" then mode = ColorMode.INDEXED end
    local created = Sprite(params.width, params.height, mode)
    if not created then error("cannot create sprite") end
    if params.file and params.file ~= "" then created:saveAs(params.file) end
    _G._mcp_created_sprite = created  -- 供生成程序引导阶段引用
    return {width = created.width, height = created.height, color_mode = params.color_mode}
end

function _G._mcp_op_save_sprite(sprite, params)
    if params.path and params.path ~= "" then
        sprite:saveAs(params.path)
        return {saved = true, path = params.path}
    end
    sprite:save()
    return {saved = (sprite.filename ~= nil and sprite.filename ~= ""), path = sprite.filename or ""}
end

function _G._mcp_op_open_sprite(sprite, params)
    local opened = app.open(params.path)
    if not opened then error("cannot open: " .. tostring(params.path)) end
    if params.file and params.file ~= "" then opened:saveAs(params.file) end
    _G._mcp_created_sprite = opened
    return {width = opened.width, height = opened.height, frames = #opened.frames}
end
