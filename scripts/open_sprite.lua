-- open_sprite.lua：打开已有文件并复制到会话工作目录
-- 参数: source (源文件路径), dest (目标 .ase 路径)
-- 调用: aseprite -b --script open_sprite.lua --script-param source=xxx.png --script-param dest=canvas.ase

local source = app.params["source"]
local dest = app.params["dest"]

if not source or not dest then
    print("ERROR: source and dest are required")
    return
end

-- 打开源文件
local sprite = app.open(source)
if not sprite then
    print("ERROR: cannot open file: " .. source)
    return
end

-- 另存为目标 .ase 文件
sprite:saveAs(dest)
print("OK: opened " .. source .. " and saved to " .. dest)
