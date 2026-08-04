-- undo.lua：撤销上一步操作
-- Live 模式: app.command.Undo()
-- CLI 模式: 由 Python 端用文件备份实现

if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite")
    return
end

app.activeSprite = sprite

local ok, err = pcall(function()
    app.command.Undo()
end)
if not ok then
    print("ERROR: undo failed: " .. tostring(err))
    return
end

_mcp_maybe_save(sprite, file)
print("OK: undo")