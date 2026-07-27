-- set_layer_properties.lua：设置图层属性
-- 参数: file (CLI 模式必需，Live 模式可省略), layer (名称或索引), name (可选), visible (可选 "true"/"false"),
--       opacity (可选 0-255), blend_mode (可选字符串)
-- 调用: aseprite -b --script set_layer_properties.lua --script-param file=canvas.ase --script-param layer=1 --script-param opacity=128
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
local layer_param = app.params["layer"]

if not layer_param then
    print("ERROR: layer is required")
    return
end

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite = _G._mcp_get_sprite(file)
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

local layer = find_layer(sprite, layer_param)
if not layer then
    print("ERROR: layer not found: " .. layer_param)
    return
end

-- 混合模式字符串到常量的映射表
local blend_modes = {
    normal = BlendMode.NORMAL,
    multiply = BlendMode.MULTIPLY,
    screen = BlendMode.SCREEN,
    overlay = BlendMode.OVERLAY,
    darken = BlendMode.DARKEN,
    lighten = BlendMode.LIGHTEN,
    addition = BlendMode.ADDITION,
    subtract = BlendMode.SUBTRACT,
    difference = BlendMode.DIFFERENCE,
    exclusion = BlendMode.EXCLUSION,
}

-- 设置名称（如果提供且非空）
local new_name = app.params["name"]
if new_name and new_name ~= "" then
    layer.name = new_name
end

-- 设置可见性（如果提供且非空）
local visible = app.params["visible"]
if visible and visible ~= "" then
    layer.isVisible = (visible == "true")
end

-- 设置不透明度（如果提供且非空）
local opacity = app.params["opacity"]
if opacity and opacity ~= "" then
    layer.opacity = tonumber(opacity)
end

-- 设置混合模式（如果提供且非空）
local blend_mode = app.params["blend_mode"]
if blend_mode and blend_mode ~= "" then
    local mode = blend_modes[blend_mode]
    if mode then
        layer.blendMode = mode
    end
end

-- 保存：Live 模式跳过，CLI 模式保存
_mcp_maybe_save(sprite, file)
print("OK: updated layer properties for '" .. layer_param .. "'")
