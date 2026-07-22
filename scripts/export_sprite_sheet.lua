-- export_sprite_sheet.lua：导出精灵表（Sprite Sheet）
-- 参数: file, output (PNG 路径), columns (可选, 默认 0=自动), data_output (可选 JSON 路径), type (可选: "horizontal"/"vertical"/"rows"/"columns"/"packed", 默认 "horizontal")
-- 调用: aseprite -b --script export_sprite_sheet.lua --script-param file=canvas.ase --script-param output=sheet.png --script-param type=horizontal

local file = app.params["file"]
local output = app.params["output"]
local columns = tonumber(app.params["columns"] or "0")
local data_output = app.params["data_output"] or ""
local sheet_type = app.params["type"] or "horizontal"

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

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
