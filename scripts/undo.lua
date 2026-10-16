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

-- app.command.Undo() on an empty history is a silent no-op that still "succeeds", so the
-- command result is not evidence. Fingerprint the document before and after instead and
-- report NOTHING when nothing moved: a caller told ok=true for a no-op undo trusts a lie.
local function fingerprint(sp)
    local parts = {
        tostring(#sp.layers), tostring(#sp.frames),
        tostring(sp.isModified and 1 or 0), tostring(sp.width), tostring(sp.height),
    }
    local layer = sp.layers[1]
    if not layer then return table.concat(parts, "/") end
    local cel = layer:cel(1)
    if not cel then return table.concat(parts, "/") end
    local image = cel.image
    local w, h = image.width, image.height
    -- exact for sprite-sized canvases; sampled above that, where hashing every pixel
    -- would cost more than the undo itself
    local step = 1
    if w * h > 65536 then step = math.floor(math.sqrt(w * h / 4096)) + 1 end
    local acc = 0
    for y = 0, h - 1, step do
        for x = 0, w - 1, step do
            local px = image:getPixel(x, y)
            acc = (acc + x * 7 + y * 13 + px) % 1000003
        end
    end
    parts[#parts + 1] = tostring(step) .. ":" .. tostring(acc)
    return table.concat(parts, "/")
end

local before = fingerprint(sprite)

local ok, err = pcall(function()
    app.command.Undo()
end)
if not ok then
    print("ERROR: undo failed: " .. tostring(err))
    return
end

if fingerprint(sprite) == before then
    print("NOTHING: undo (Aseprite history is empty or the document is unchanged)")
    return
end

_mcp_maybe_save(sprite, file)
print("OK: undo")