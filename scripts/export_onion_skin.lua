-- export_onion_skin.lua：导出洋葱皮叠加预览 PNG
-- 参数: file, output (PNG 路径), frame (中心帧号 1-indexed), scale
-- 行为: 前一帧(红半透明) + 当前帧(原色) + 后一帧(蓝半透明) 叠加导出
local file = app.params["file"]
local output = app.params["output"]
local frame_idx = tonumber(app.params["frame"] or "1")
local scale = tonumber(app.params["scale"] or "1")

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
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
