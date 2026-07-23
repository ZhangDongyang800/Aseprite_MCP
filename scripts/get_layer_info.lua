-- get_layer_info.lua：获取所有图层信息，输出 JSON 数组
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略)
-- 输出: JSON 数组，每个元素包含 name, index, visible, opacity, blend_mode, is_background, is_group
-- 调用: aseprite -b --script get_layer_info.lua --script-param file=canvas.ase
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
-- CLI 模式行为：
--   - 从 file 打开 sprite（只读，不保存）

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]

-- 获取 sprite：Live 模式用 activeSprite，CLI 模式用 app.open(file)
local sprite
if _G._mcp_get_sprite then
    sprite = _G._mcp_get_sprite(file)
else
    sprite = file and app.open(file) or app.activeSprite
end
if not sprite then
    print('{"error": "no active sprite. Call create_sprite first, or provide file parameter."}')
    return
end

-- 混合模式常量反向映射为字符串名称
local function blend_mode_to_string(mode)
    if mode == BlendMode.NORMAL then return "normal"
    elseif mode == BlendMode.MULTIPLY then return "multiply"
    elseif mode == BlendMode.SCREEN then return "screen"
    elseif mode == BlendMode.OVERLAY then return "overlay"
    elseif mode == BlendMode.DARKEN then return "darken"
    elseif mode == BlendMode.LIGHTEN then return "lighten"
    elseif mode == BlendMode.ADDITION then return "addition"
    elseif mode == BlendMode.SUBTRACT then return "subtract"
    elseif mode == BlendMode.DIFFERENCE then return "difference"
    elseif mode == BlendMode.EXCLUSION then return "exclusion"
    else return "normal" end
end

-- JSON 字符串转义（处理特殊字符，防止 JSON 格式错误）
local function escape_json_string(s)
    s = s:gsub('\\', '\\\\')
    s = s:gsub('"', '\\"')
    return s
end

-- 构建 JSON 数组，遍历所有图层
local parts = {}
for i, layer in ipairs(sprite.layers) do
    local layer_json = string.format(
        '{"name": "%s", "index": %d, "visible": %s, "opacity": %d, "blend_mode": "%s", "is_background": %s, "is_group": %s}',
        escape_json_string(layer.name),
        i,
        tostring(layer.isVisible),
        layer.opacity,
        blend_mode_to_string(layer.blendMode),
        tostring(layer.isBackground),
        tostring(layer.isGroup)
    )
    table.insert(parts, layer_json)
end

local json = "[" .. table.concat(parts, ", ") .. "]"
print(json)
