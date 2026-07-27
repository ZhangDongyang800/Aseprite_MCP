-- mcp_common.lua：Live/CLI 双模式兼容辅助模块
-- 通过 dofile 加载，在全局命名空间设置辅助函数。
--
-- 用法：在脚本开头加一行 dofile(...)
--   Live 模式：extension/main.lua 在 dofile 主脚本前先 dofile 本文件
--   CLI 模式：主脚本自己 dofile 本文件（路径通过 scripts_dir 推导）
--
-- 核心函数：
--   _mcp_get_sprite(file): Live 模式优先用 app.activeSprite，CLI 模式用 app.open(file)
--   _mcp_maybe_save(sprite, file): Live 模式跳过保存，CLI 模式保存
--   _mcp_is_live: 是否在 Live 模式（WebSocket 扩展环境）

-- 防止重复加载
if _G._mcp_common_loaded then
    return
end
_G._mcp_common_loaded = true

-- Live 模式标志：由 extension/main.lua 设置
-- 如果 _G._mcp_live_mode 未设置，说明在 CLI 模式下
_G._mcp_is_live = (_G._mcp_live_mode == true)

-- 获取 sprite：Live 模式优先用 app.activeSprite
-- 参数:
--   file: .ase 文件路径（CLI 模式必需，Live 模式可选）
-- 返回:
--   sprite 对象，或 nil + 错误信息
_G._mcp_get_sprite = function(file)
    -- Live 模式：优先用当前打开的 sprite
    if _G._mcp_is_live and app.activeSprite then
        return app.activeSprite
    end
    -- CLI 模式或 Live 模式但无 active sprite：从文件打开
    if file and file ~= "" then
        local sprite = app.open(file)
        if not sprite then
            return nil, "cannot open file: " .. file
        end
        return sprite
    end
    -- Live 模式但无 active sprite 且无 file 参数
    if _G._mcp_is_live then
        return nil, "no active sprite. Call create_sprite first."
    end
    return nil, "no file specified and not in live mode"
end

-- 保存 sprite：Live 模式跳过（UI 实时显示），CLI 模式保存
-- 参数:
--   sprite: sprite 对象
--   file: .ase 文件路径（CLI 模式必需）
_G._mcp_maybe_save = function(sprite, file)
    -- Live 模式下不自动保存：用户在 Aseprite 中能实时看到变化
    -- 如果需要保存到文件，用户可显式调用 save_sprite 工具
    if _G._mcp_is_live then
        return
    end
    -- CLI 模式：保存到文件
    if file and file ~= "" and sprite then
        sprite:saveAs(file)
    end
end

-- 获取或创建 sprite：用于 create_sprite 工具
-- Live 模式下如果已有 active sprite 且尺寸/模式匹配，则复用
-- 参数:
--   width, height, color_mode: 期望的尺寸和颜色模式
--   file: 输出文件路径（CLI 模式必需）
-- 返回:
--   sprite 对象, created (bool: true=新建, false=复用)
_G._mcp_get_or_create_sprite = function(width, height, color_mode, file)
    -- 映射颜色模式字符串到 ColorMode 常量
    local mode
    if color_mode == "rgb" then
        mode = ColorMode.RGB
    elseif color_mode == "grayscale" then
        mode = ColorMode.GRAYSCALE
    elseif color_mode == "indexed" then
        mode = ColorMode.INDEXED
    else
        mode = ColorMode.RGB
    end

    -- Live 模式：检查是否可复用当前 sprite
    if _G._mcp_is_live and app.activeSprite then
        local s = app.activeSprite
        if s.width == width and s.height == height then
            -- 尺寸匹配，复用
            return s, false
        end
        -- 尺寸不匹配，关闭旧的，创建新的
        -- 注意：不自动关闭，让用户决定。直接新建会切换 active sprite
    end

    -- 创建新 sprite
    local sprite = Sprite(width, height, mode)
    if not sprite then
        return nil, false
    end

    -- CLI 模式：保存到文件
    if not _G._mcp_is_live and file and file ~= "" then
        sprite:saveAs(file)
    end

    return sprite, true
end

-- 解析十六进制颜色 #RRGGBB 为 r, g, b 值
-- 参数: hex (#RRGGBB 格式字符串，如 "#FF0000")
-- 返回: r, g, b 三个整数
_G._mcp_hex_to_rgb = function(hex)
    local r = tonumber(hex:sub(2, 3), 16)
    local g = tonumber(hex:sub(4, 5), 16)
    local b = tonumber(hex:sub(6, 7), 16)
    return r, g, b
end

-- 获取指定图层/帧的 image，如果 cel 不存在则自动创建
-- 参数: sprite, layer_idx (1-based), frame_idx (1-based)
-- 返回: image 对象，或 nil + 错误信息
_G._mcp_get_target_image = function(sprite, layer_idx, frame_idx)
    local target_layer = sprite.layers[layer_idx]
    if not target_layer then
        return nil, "layer not found: " .. tostring(layer_idx)
    end
    local cel = target_layer:cel(frame_idx)
    if not cel then
        cel = sprite:newCel(target_layer, frame_idx)
    end
    return cel.image
end
