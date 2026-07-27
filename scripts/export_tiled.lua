-- export_tiled.lua：把当前画布当单个瓦片，导出 repeat×repeat 拼接预览 PNG
-- 参数: file (CLI 模式必需，Live 模式可省略), output (必填), repeat (重复次数，默认 2), scale (默认 1)
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 导出拼接预览到 output 路径
-- CLI 模式行为：
--   - 从 file 打开 sprite，导出拼接预览到 output

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local output = app.params["output"]
local rep = tonumber(app.params["repeat"] or "2")
local scale = tonumber(app.params["scale"] or "1")

-- 参数校验：output 为必填，file 在 Live 模式下可省略
if not output then
    print("ERROR: output is required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

local w = sprite.width
local h = sprite.height
local layer = sprite.layers[1]
local cel = layer:cel(1)
if not cel or not cel.image then
    print("ERROR: no image in frame 1")
    return
end
local src = cel.image

-- 创建拼接后的画布
local out_w = w * rep
local out_h = h * rep
local result = Image(out_w, out_h, sprite.colorMode)
result:clear()

-- 平铺复制
for ry = 0, rep - 1 do
    for rx = 0, rep - 1 do
        result:drawImage(src, rx * w, ry * h)
    end
end

-- 导出：用临时 sprite 承载拼接结果并保存为 PNG
local tmp_sprite = Sprite(out_w, out_h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(result)
if scale > 1 then
    tmp_sprite:resize(out_w * scale, out_h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print("OK: exported tiled preview " .. rep .. "x" .. rep .. " to " .. output)
