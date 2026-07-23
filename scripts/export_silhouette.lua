-- export_silhouette.lua：导出纯黑剪影 PNG（docs §3.6 剪影测试）
-- 参数: file (CLI 模式必需，Live 模式可省略), output (PNG 路径，必填), scale
-- 行为: 所有非透明像素 -> 黑色，导出
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 导出剪影到 output 路径
-- CLI 模式行为：
--   - 从 file 打开 sprite，导出剪影到 output

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local output = app.params["output"]
local scale = tonumber(app.params["scale"] or "1")

-- 参数校验：output 为必填，file 在 Live 模式下可省略
if not output then
    print("ERROR: output is required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite
if _G._mcp_get_sprite then
    sprite = _G._mcp_get_sprite(file)
else
    sprite = file and app.open(file) or app.activeSprite
end
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
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
