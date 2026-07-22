-- load_palette.lua：从文件加载调色板
-- 参数: file (会话 .ase 路径), palette_file (调色板文件路径，支持 .gpl/.pal/.png)
-- 调用: aseprite -b --script load_palette.lua --script-param file=canvas.ase --script-param palette_file=pal.gpl

local file = app.params["file"]
local palette_file = app.params["palette_file"]

if not file or not palette_file then
    print("ERROR: file and palette_file are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- 从外部文件加载调色板到当前精灵
sprite:loadPalette(palette_file)

-- 保存并输出
sprite:saveAs(file)
print("OK: loaded palette from " .. palette_file)
