-- move_cel.lua：将 cel 从源图层/帧移动到目标图层/帧
-- 参数: file (CLI 模式必需，Live 模式可省略), source_layer (名称或索引), source_frame (1-based),
--       dest_layer (名称或索引), dest_frame (1-based)
-- 调用: aseprite -b --script move_cel.lua --script-param file=canvas.ase
--   --script-param source_layer=1 --script-param source_frame=1
--   --script-param dest_layer=2 --script-param dest_frame=1
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 修改实时反映在 Aseprite UI 上
-- CLI 模式行为：
--   - 从 file 打开 sprite，修改后保存回 file

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local source_layer_param = app.params["source_layer"]
local source_frame = app.params["source_frame"]
local dest_layer_param = app.params["dest_layer"]
local dest_frame = app.params["dest_frame"]

if not source_layer_param or not source_frame or not dest_layer_param or not dest_frame then
    print("ERROR: source_layer, source_frame, dest_layer, dest_frame are required")
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

-- 根据名称或索引查找图层
local function find_layer(spr, param)
    local num = tonumber(param)
    if num then
        -- 数字索引查找
        return spr.layers[num]
    end
    -- 按名称遍历查找
    for _, l in ipairs(spr.layers) do
        if l.name == param then
            return l
        end
    end
    return nil
end

local source_layer = find_layer(sprite, source_layer_param)
local dest_layer = find_layer(sprite, dest_layer_param)

if not source_layer then
    print("ERROR: source layer not found: " .. source_layer_param)
    return
end
if not dest_layer then
    print("ERROR: destination layer not found: " .. dest_layer_param)
    return
end

-- 获取源帧对应的 Frame 对象，并取出源 cel
local source_frame_obj = sprite.frames[tonumber(source_frame)]
local source_cel = source_layer:cel(source_frame_obj)
if not source_cel then
    print("ERROR: no cel found at source layer/frame")
    return
end

-- 克隆源 cel 的图像
local new_image = source_cel.image:clone()

-- 在目标图层/帧创建新 cel，使用克隆图像和原始位置
local dest_frame_obj = sprite.frames[tonumber(dest_frame)]
sprite:newCel(dest_layer, dest_frame_obj, new_image, source_cel.position)

-- 删除原始 cel
sprite:deleteCel(source_cel)

-- 保存：Live 模式跳过，CLI 模式保存
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, file)
else
    if file and file ~= "" then
        sprite:saveAs(file)
    end
end
print("OK: moved cel from layer '" .. source_layer_param .. "' frame " .. source_frame ..
      " to layer '" .. dest_layer_param .. "' frame " .. dest_frame)
