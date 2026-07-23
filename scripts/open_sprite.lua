-- open_sprite.lua：打开已有文件并复制到会话工作目录
-- 参数: source (源文件路径), dest (目标 .ase 路径，CLI 模式必需，Live 模式可省略)
-- 调用: aseprite -b --script open_sprite.lua --script-param source=xxx.png --script-param dest=canvas.ase
--
-- Live 模式行为：
--   - 打开 source 文件并设为 active sprite
--   - dest 参数可省略（不强制保存副本）
-- CLI 模式行为：
--   - 打开 source 文件并另存为 dest

-- 加载公共辅助模块（CLI 模式下需要，Live 模式下已被 main.lua 预加载）
if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local source = app.params["source"]
local dest = app.params["dest"]

if not source then
    print("ERROR: source is required")
    return
end

-- 打开源文件
local sprite = app.open(source)
if not sprite then
    print("ERROR: cannot open file: " .. source)
    return
end

-- CLI 模式：另存为目标 .ase 文件；Live 模式：跳过（sprite 已打开并设为 active）
if _G._mcp_maybe_save then
    _G._mcp_maybe_save(sprite, dest)
else
    if dest and dest ~= "" then
        sprite:saveAs(dest)
    end
end
print("OK: opened " .. source .. (dest and (" and saved to " .. dest) or " (live mode)"))
