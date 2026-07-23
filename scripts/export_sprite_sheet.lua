-- export_sprite_sheet.lua：导出精灵表（Sprite Sheet）
-- 参数: file (CLI 模式必需，Live 模式可省略), output (PNG 路径，必填), columns (可选, 默认 0=自动), data_output (可选 JSON 路径), type (可选: "horizontal"/"vertical"/"rows"/"columns"/"packed", 默认 "horizontal")
-- 调用: aseprite -b --script export_sprite_sheet.lua --script-param file=canvas.ase --script-param output=sheet.png --script-param type=horizontal
--
-- Live 模式行为：
--   - 优先使用 app.activeSprite（无需 file 参数）
--   - 导出精灵表到 output 路径
-- CLI 模式行为：
--   - 从 file 打开 sprite，导出精灵表到 output

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local output = app.params["output"]
local columns = tonumber(app.params["columns"] or "0")
local data_output = app.params["data_output"] or ""
local sheet_type = app.params["type"] or "horizontal"

-- 参数校验：output 为必填（导出路径不可省略），file 在 Live 模式下可省略
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

-- 设置为活动精灵（ExportSpriteSheet 命令作用于 activeSprite）
app.activeSprite = sprite

-- 映射类型字符串到 SpriteSheetType 常量
local sheet_type_const
if sheet_type == "horizontal" then
    sheet_type_const = SpriteSheetType.HORIZONTAL
elseif sheet_type == "vertical" then
    sheet_type_const = SpriteSheetType.VERTICAL
elseif sheet_type == "rows" then
    sheet_type_const = SpriteSheetType.ROWS
elseif sheet_type == "columns" then
    sheet_type_const = SpriteSheetType.COLUMNS
elseif sheet_type == "packed" then
    sheet_type_const = SpriteSheetType.PACKED
else
    print("ERROR: invalid type: " .. sheet_type .. " (expected: horizontal, vertical, rows, columns, packed)")
    return
end

-- 构造导出参数表
local export_params = {
    ui = false,
    type = sheet_type_const,
    columns = columns,
    textureFilename = output,
    dataFormat = SpriteSheetDataFormat.JSON_HASH,
}

-- 如果提供了数据输出路径，则添加 dataFilename
if data_output and data_output ~= "" then
    export_params.dataFilename = data_output
end

-- 执行精灵表导出命令
app.command.ExportSpriteSheet(export_params)
print("OK: exported sprite sheet to " .. output)
