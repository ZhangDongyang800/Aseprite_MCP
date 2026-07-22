-- export_silhouette.lua：导出纯黑剪影 PNG（docs §3.6 剪影测试）
-- 参数: file, output (PNG 路径), scale
-- 行为: 所有非透明像素 -> 黑色，导出
local file = app.params["file"]
local output = app.params["output"]
local scale = tonumber(app.params["scale"] or "1")

-- 参数校验：file 和 output 必填
if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 取第 1 帧第 1 层的图像作为剪影来源
local w = sprite.width
local h = sprite.height
local layer = sprite.layers[1]
local cel = layer:cel(1)
if not cel or not cel.image then
    print("ERROR: no image in frame 1")
    return
end
local src = cel.image

-- 创建剪影 Image（与源图同尺寸同色彩模式）
local silhouette = Image(w, h, sprite.colorMode)
silhouette:clear()
-- 纯黑色：用于填充剪影（docs §3.6 角色识别度检查）
local black = app.pixelColor.rgba(0, 0, 0, 255)

-- 遍历源图像素：非透明像素（alpha>0）在剪影上画黑
for it in src:pixels() do
    local pc = it()
    if app.pixelColor.rgbaA(pc) > 0 then
        silhouette:drawPixel(it.x, it.y, black)
    end
end

-- 导出：用临时 sprite 承载剪影图像并保存为 PNG
local tmp_sprite = Sprite(w, h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(silhouette)
-- 按需放大（便于视觉检查轮廓识别度）
if scale > 1 then
    tmp_sprite:resize(w * scale, h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print("OK: exported silhouette to " .. output)
