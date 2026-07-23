-- save_sprite.lua：将会话画布另存为指定格式
-- 参数: file (会话 .ase 路径，CLI 模式必需，Live 模式可省略), output (输出路径，.ase 或 .png)
-- 调用: aseprite -b --script save_sprite.lua --script-param file=canvas.ase --script-param output=result.png
--
-- Live 模式行为：
--   - 使用 app.activeSprite 作为源
--   - 通过 saveCopyAs 导出副本到 output 路径
-- CLI 模式行为：
--   - 从 file 打开 sprite，通过 saveCopyAs 导出副本到 output 路径

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local output = app.params["output"]

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

-- saveCopyAs 不会改变当前文件的路径
sprite:saveCopyAs(output)
print("OK: saved to " .. output)
