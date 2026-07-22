-- save_sprite.lua：将会话画布另存为指定格式
-- 参数: file (会话 .ase 路径), output (输出路径，.ase 或 .png)
-- 调用: aseprite -b --script save_sprite.lua --script-param file=canvas.ase --script-param output=result.png

local file = app.params["file"]
local output = app.params["output"]

if not file or not output then
    print("ERROR: file and output are required")
    return
end

local sprite = app.open(file)
if not sprite then
    print("ERROR: cannot open file: " .. file)
    return
end

-- saveCopyAs 不会改变当前文件的路径
sprite:saveCopyAs(output)
print("OK: saved to " .. output)
