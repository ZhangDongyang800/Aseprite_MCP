-- batch_edit.lua：在单次 Aseprite 进程中执行多个操作
-- 参数: file, operations (JSON 数组字符串)
-- 每个 operation: {"script": "xxx.lua", "params": {...}}
-- 所有操作按顺序执行，结果汇总为 JSON 数组返回

if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then
        pcall(dofile, script_dir .. "mcp_common.lua")
    end
end

local file = app.params["file"]
local operations_str = app.params["operations"]

if not operations_str or operations_str == "" then
    print('{"error":"operations parameter is required"}')
    return
end

-- Aseprite Lua 没有内置 JSON 解析器，使用简单的字符串解析
-- 预期格式: script1 k1=v1 k2=v2 ; script2 k1=v1 k2=v2
-- 即用 ; 分隔操作，每个操作前是脚本名，后面是空格分隔的 key=value 对

local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print('{"error":"no active sprite"}')
    return
end

-- 确保 sprite 是活跃的
app.activeSprite = sprite

local function parse_operations(str)
    local ops = {}
    -- 按 ; 分割
    for op_str in str:gmatch("[^;]+") do
        op_str = op_str:gsub("^%s+", ""):gsub("%s+$", "")
        if op_str ~= "" then
            -- 分割为 tokens: 第一个是脚本名，后面是 key=value 对
            local tokens = {}
            for token in op_str:gmatch("%S+") do
                table.insert(tokens, token)
            end
            if #tokens > 0 then
                local op = {script = tokens[1], params = {}}
                for i = 2, #tokens do
                    local k, v = tokens[i]:match("([^=]+)=(.+)")
                    if k and v then
                        -- 反转义特殊字符
                        v = v:gsub("\\t", "\t"):gsub("\\n", "\n"):gsub("\\=", "="):gsub("\\\\", "\\")
                        op.params[k] = v
                    end
                end
                table.insert(ops, op)
            end
        end
    end
    return ops
end

local ops = parse_operations(operations_str)
if #ops == 0 then
    print('{"error":"no valid operations found"}')
    return
end

local results = {}
local success_count = 0
local fail_count = 0

for i, op in ipairs(ops) do
    -- 构造脚本文件路径
    local script_path = op.script
    -- 如果 script 不包含路径分隔符，从当前脚本目录推导
    if not script_path:match("[/\\]") then
        local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
        if script_dir then
            script_path = script_dir .. op.script
        end
    end

    -- 检查脚本是否存在
    local sf = io.open(script_path, "r")
    if not sf then
        fail_count = fail_count + 1
        table.insert(results, {step = i, script = op.script, success = false, error = "script not found: " .. script_path})
        goto continue
    end
    sf:close()

    -- 设置 app.params
    local old_params = {}
    for k, v in pairs(app.params) do
        old_params[k] = v
    end

    app.params = {}
    app.params["file"] = file
    for k, v in pairs(op.params) do
        app.params[k] = v
    end

    -- 执行脚本并捕获输出
    local captured = {}
    local old_print = _G.print
    _G.print = function(...)
        local args = {...}
        local strs = {}
        for j = 1, #args do
            strs[j] = tostring(args[j])
        end
        captured[#captured + 1] = table.concat(strs, "\t")
    end

    local ok, err = pcall(function()
        dofile(script_path)
    end)

    _G.print = old_print

    -- 恢复 app.params
    app.params = old_params

    local stdout = table.concat(captured, "\n")
    if ok then
        success_count = success_count + 1
        table.insert(results, {step = i, script = op.script, success = true, stdout = stdout})
    else
        fail_count = fail_count + 1
        table.insert(results, {step = i, script = op.script, success = false, error = tostring(err), stdout = stdout})
    end

    ::continue::
end

-- 保存
_mcp_maybe_save(sprite, file)

-- 输出汇总 JSON（手动构造，避免依赖 JSON 库）
local parts = {}
table.insert(parts, '"success":' .. tostring(fail_count == 0))
table.insert(parts, '"total":' .. #ops)
table.insert(parts, '"succeeded":' .. success_count)
table.insert(parts, '"failed":' .. fail_count)
table.insert(parts, '"results":[')
for i, r in ipairs(results) do
    local rparts = {}
    table.insert(rparts, '"step":' .. r.step)
    table.insert(rparts, '"script":"' .. r.script .. '"')
    table.insert(rparts, '"success":' .. tostring(r.success))
    if r.stdout and r.stdout ~= "" then
        -- 转义 stdout 中的特殊字符
        local esc = r.stdout:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\t", "\\t")
        table.insert(rparts, '"stdout":"' .. esc .. '"')
    end
    if r.error then
        local esc = r.error:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\t", "\\t")
        table.insert(rparts, '"error":"' .. esc .. '"')
    end
    table.insert(parts, "{" .. table.concat(rparts, ",") .. "}")
    if i < #results then table.insert(parts, ",") end
end
table.insert(parts, "]")
print("{" .. table.concat(parts) .. "}")