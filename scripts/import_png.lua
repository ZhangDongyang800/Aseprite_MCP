-- import_png.lua：从 PNG 文件导入到 sprite（双模式）
-- 这是画任意图像的最省 token 方式：AI 用 Python/PIL 生成 PNG，再导入 Aseprite。
--
-- 两种模式：
--   mode=new   从 PNG 创建新 sprite，保存到 dest.ase，输出 {width,height} JSON
--   mode=stamp 把 PNG 贴到当前会话 sprite 的指定 layer/frame/offset 位置
--
-- 参数:
--   png_path (必填)              PNG 文件路径
--   mode     (必填)              "new" 或 "stamp"
--   dest     (new 模式必填)      目标 .ase 输出路径
--   file     (stamp 模式必填)    当前会话 .ase 路径
--   layer, frame, offset_x, offset_y (stamp 模式参数，默认 1/1/0/0)
--
-- 调用示例:
--   new:   aseprite -b --script import_png.lua \
--            --script-param png_path=in.png --script-param mode=new --script-param dest=canvas.ase
--   stamp: aseprite -b --script import_png.lua \
--            --script-param png_path=stamp.png --script-param mode=stamp --script-param file=canvas.ase \
--            --script-param layer=1 --script-param frame=1 --script-param offset_x=5 --script-param offset_y=5
--
-- 输出: JSON 字符串
--   new   模式成功: {"width": 32, "height": 32}
--   stamp 模式成功: {"ok": "stamped png onto layer 1 frame 1 at (5,5)"}
--   失败:           {"error": "..."}

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local png_path = app.params["png_path"]
local mode = app.params["mode"] or "new"
local dest = app.params["dest"]
local file = app.params["file"]

if not png_path then
    print('{"error": "png_path is required"}')
    return
end

-- 打开 PNG 源文件
local png_sprite = app.open(png_path)
if not png_sprite then
    print('{"error": "failed to open png: ' .. png_path .. '"}')
    return
end

if mode == "new" then
    -- new 模式：PNG sprite 直接另存为 .ase
    if not dest or dest == "" then
        print('{"error": "dest is required for new mode"}')
        return
    end
    png_sprite:saveAs(dest)
    local w, h = png_sprite.width, png_sprite.height
    -- 关闭 png sprite，避免遗留活动 sprite
    png_sprite:close()
    -- 输出尺寸 JSON 供 Python 解析
    print(string.format('{"width": %d, "height": %d}', w, h))

elseif mode == "stamp" then
    -- stamp 模式：把 PNG 像素贴到当前会话 sprite 的指定位置
    if not file or file == "" then
        print('{"error": "file is required for stamp mode"}')
        return
    end
    -- 获取会话 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
    local sprite
    if _G._mcp_get_sprite then
        sprite = _G._mcp_get_sprite(file)
    else
        sprite = app.open(file)
    end
    if not sprite then
        print('{"error": "no active sprite. Call create_sprite first, or provide file parameter."}')
        return
    end

    local layer_idx = tonumber(app.params["layer"] or "1")
    local frame_idx = tonumber(app.params["frame"] or "1")
    local offset_x = tonumber(app.params["offset_x"] or "0")
    local offset_y = tonumber(app.params["offset_y"] or "0")

    local target_layer = sprite.layers[layer_idx]
    if not target_layer then
        print('{"error": "layer not found: ' .. layer_idx .. '"}')
        return
    end
    local cel = target_layer:cel(frame_idx)
    if not cel then
        cel = sprite:newCel(target_layer, frame_idx)
    end
    local image = cel.image

    -- 取 PNG 第1层第1帧的 image（PNG 通常只有一个 cel）
    local png_layer = png_sprite.layers[1]
    local png_cel = png_layer:cel(1)
    if not png_cel or not png_cel.image then
        print('{"error": "png has no image on layer 1 frame 1"}')
        return
    end
    -- 把 PNG image 绘制到目标 cel image 的 offset 位置
    image:drawImage(png_cel.image, offset_x, offset_y)

    -- 保存会话 .ase：Live 模式跳过，CLI 模式保存
    if _G._mcp_maybe_save then
        _G._mcp_maybe_save(sprite, file)
    else
        sprite:saveAs(file)
    end
    png_sprite:close()
    print(string.format(
        '{"ok": "stamped png onto layer %d frame %d at (%d,%d)"}',
        layer_idx, frame_idx, offset_x, offset_y
    ))

else
    print('{"error": "invalid mode: ' .. mode .. '. Must be new or stamp"}')
end
