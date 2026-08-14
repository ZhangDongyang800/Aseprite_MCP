-- export_contact_sheet.lua：多帧动画总览图（contact sheet）
-- 参数: file (CLI 模式必需，Live 模式可省略), output (PNG 路径，必填),
--       start_frame (可选，默认 1), end_frame (可选，默认最后一帧),
--       columns (可选，默认 0=单行横排), ghost (可选 "1"/"0"，默认 "1" 叠加前一帧红色幽灵), scale
--
-- 用途: 一次返回整条动画序列的大图，让 AI 不用逐帧 preview 就能检查连贯性。
-- ghost=1 时每帧下方叠加前一帧的红色半透明轮廓，帧间差异一目了然。

if not _G._mcp_common_loaded then
    local script_dir = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if script_dir then pcall(dofile, script_dir .. "mcp_common.lua") end
end

local file = app.params["file"]
local output = app.params["output"]
local start_frame = tonumber(app.params["start_frame"] or "1")
local end_frame = tonumber(app.params["end_frame"] or "0")
local columns = tonumber(app.params["columns"] or "0")
local ghost = app.params["ghost"] ~= "0"
local scale = tonumber(app.params["scale"] or "1")

if not output then
    print("ERROR: output is required")
    return
end

local sprite = _G._mcp_get_sprite(file)
if not sprite then
    print("ERROR: no active sprite. Call create_sprite first, or provide file parameter.")
    return
end

local frame_count = #sprite.frames
if end_frame == 0 or end_frame > frame_count then end_frame = frame_count end
if start_frame < 1 then start_frame = 1 end
if start_frame > end_frame then
    print("ERROR: start_frame must be <= end_frame")
    return
end

local w, h = sprite.width, sprite.height
local n = end_frame - start_frame + 1
local cols = columns > 0 and columns or n
local rows = math.ceil(n / cols)
local pad = 2 -- 帧间距像素，便于观察

-- 合成某帧全部图层为一张画布图（考虑 cel.position 偏移）
local function composite(frame_no)
    local img = Image(w, h, sprite.colorMode)
    img:clear()
    for li = 1, #sprite.layers do
        local layer = sprite.layers[li]
        local cel = layer:cel(frame_no)
        if cel and cel.image then
            local px, py = cel.position.x, cel.position.y
            img:drawImage(cel.image, px, py)
        end
    end
    return img
end

-- 取某帧的"轮廓幽灵"（非透明像素染红半透明，用于 ghost 叠加）
local function ghost_outline(frame_no)
    local img = Image(w, h, sprite.colorMode)
    img:clear()
    for li = 1, #sprite.layers do
        local layer = sprite.layers[li]
        local cel = layer:cel(frame_no)
        if cel and cel.image then
            local px, py = cel.position.x, cel.position.y
            for it in cel.image:pixels() do
                local pc = it()
                local a = app.pixelColor.rgbaA(pc)
                if a > 0 then
                    local r = app.pixelColor.rgbaR(pc)
                    local g = app.pixelColor.rgbaG(pc)
                    local b = app.pixelColor.rgbaB(pc)
                    local mr = math.floor(r * 155 / 255 + 255 * 100 / 255)
                    local mg = math.floor(g * 155 / 255 + 64 * 100 / 255)
                    local mb = math.floor(b * 155 / 255 + 64 * 100 / 255)
                    img:drawPixel(it.x + px, it.y + py, app.pixelColor.rgba(mr, mg, mb, 200))
                end
            end
        end
    end
    return img
end

-- 构建总览图
local sheet_w = cols * w + (cols + 1) * pad
local sheet_h = rows * h + (rows + 1) * pad
local sheet = Image(sheet_w, sheet_h, sprite.colorMode)
sheet:clear()

for i = 0, n - 1 do
    local frame_no = start_frame + i
    local cx = pad + (i % cols) * (w + pad)
    local cy = pad + math.floor(i / cols) * (h + pad)
    if ghost and frame_no > start_frame then
        sheet:drawImage(ghost_outline(frame_no - 1), cx, cy)
    end
    sheet:drawImage(composite(frame_no), cx, cy)
end

-- 导出
local tmp_sprite = Sprite(sheet_w, sheet_h, sprite.colorMode)
tmp_sprite.cels[1].image:drawImage(sheet)
if scale > 1 then
    tmp_sprite:resize(sheet_w * scale, sheet_h * scale)
end
tmp_sprite:saveCopyAs(output)
tmp_sprite:close()

print(string.format(
    "OK: exported contact sheet (%d frames, %dx%d grid) to %s",
    n, cols, rows, output
))
