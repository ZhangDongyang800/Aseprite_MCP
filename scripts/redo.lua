-- redo.lua：重做已撤销的操作
-- 仅在 Live 模式下有效（CLI 模式无 redo 栈）

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
    app.command.Redo()
end)
if not ok then
    print("ERROR: redo failed: " .. tostring(err))
    return
end

_mcp_maybe_save(sprite, file)
print("OK: redo")