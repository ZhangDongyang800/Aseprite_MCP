-- export_onion_skin.lua：导出洋葱皮叠加预览 PNG
-- 参数: file (CLI 模式必需，Live 模式可省略), output (PNG 路径，必填), frame (中心帧号 1-indexed), scale
-- 行为: 前一帧(红半透明) + 当前帧(原色) + 后一帧(蓝半透明) 叠加导出
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 导出洋葱皮预览到 output 路径
-- CLI 模式行为：
--   - 从 file 打开 sprite，导出洋葱皮预览到 output

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local output = app.params["output"]
local frame_idx = tonumber(app.params["frame"] or "1")
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

-- 创建叠加用的 Image（RGBA）
local result = Image(w, h, sprite.colorMode)
result:clear()

-- 工具函数：把某帧叠加到 result，tint 为 {r,g,b,a} 色调
local function overlay(frame_no, tr, tg, tb, ta)
    if not sprite.frames[frame_no] then return end
    local layer = sprite.layers[1]
    local cel = layer:cel(frame_no)
    if not cel or not cel.image then return end
    local img = cel.image
    for it in img:pixels() do
        local pc = it()
        local a = app.pixelColor.rgbaA(pc)
        if a > 0 then
            -- 取原图 rgb，应用色调与 alpha
            local r = app.pixelColor.rgbaR(pc)
            local g = app.pixelColor.rgbaG(pc)
            local b = app.pixelColor.rgbaB(pc)
            -- 色调混合：与 tint 色按 ta 混合
            local mr = math.floor(r * (255 - ta) / 255 + tr * ta / 255)
            local mg = math.floor(g * (255 - ta) / 255 + tg * ta / 255)
            local mb = math.floor(b * (255 - ta) / 255 + tb * ta / 255)
            result:drawPixel(it.x, it.y, app.pixelColor.rgba(mr, mg, mb, 255))
        end
    end
end

-- 前一帧（红色半透明，ta=100）
overlay(frame_idx - 1, 255, 0, 0, 100)
-- 当前帧（原色，ta=0 即不调色）
overlay(frame_idx, 0, 0, 0, 0)
-- 后一帧（蓝色半透明，ta=100）
overlay(frame_idx + 1, 0, 0, 255, 100)

-- 导出叠加图（用临时 sprite 保存）
local tmp_sprite = Sprite(w, h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(result)
if scale > 1 then
    tmp_sprite:resize(w * scale, h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print("OK: exported onion skin preview to " .. output)
