-- merge_down.lua：合并指定图层到下层
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end
local file = app.params["file"]
local layer_param = app.params["layer"]
local sprite = _G._mcp_get_sprite(file)
if not sprite then print("ERROR: no active sprite") return end
app.activeSprite = sprite

if layer_param and layer_param ~= "" then
    local num = tonumber(layer_param)
    if num then
        app.activeLayer = sprite.layers[num]
    else
        -- 按名称查找
        for i, l in ipairs(sprite.layers) do
            if l.name == layer_param then app.activeLayer = l; break end
        end
    end
end
app.command.MergeDownLayer()
_mcp_maybe_save(sprite, file)
print("OK: merged layer down")