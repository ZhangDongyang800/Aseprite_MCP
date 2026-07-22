"""MCP Prompts：预定义工作流模板。

基于专业像素艺术工作流设计：草图 → 线稿 → 平涂底色 → 阴影/高光 → 描边 → 导出。
参考 Aseprite 官方文档和专业游戏美术实践。
"""


def register_prompts(mcp):
    """注册 MCP Prompts。

    Args:
        mcp: FastMCP 实例
    """

    @mcp.prompt
    def create_sprite_prompt(description: str, size: str = "16x16") -> str:
        """生成精灵创作引导消息。

        Args:
            description: 想要绘制的精灵描述（如"一个红色的蘑菇"）
            size: 画布尺寸，如 16x16、32x32
        """
        # 根据画布尺寸选择坐标网格模板
        if "16" in size:
            grid_example = _GRID_16X16_TEMPLATE
            palette_suggestion = _PALETTE_SUGGESTIONS["character_16"]
        elif "32" in size:
            grid_example = _GRID_32X32_TEMPLATE
            palette_suggestion = _PALETTE_SUGGESTIONS["character_32"]
        else:
            grid_example = _GRID_16X16_TEMPLATE
            palette_suggestion = _PALETTE_SUGGESTIONS["icon"]

        return f"""请使用 Aseprite MCP 工具绘制一个精灵：{description}

══════════════════════════════════════════
专业像素艺术工作流程（草图 → 线稿 → 平涂 → 阴影 → 描边）：
══════════════════════════════════════════

第1步：创建画布
  调用 create_sprite 创建 {size} 画布

第2步：规划像素布局（关键步骤！）
  在绘制前，先用文本网格规划整个精灵的像素布局。
  这是专业像素艺术的核心——先规划再绘制，而不是边画边想。

  规划方法：
  a) 先确定配色方案（从下方参考中选择或自定义），为每种颜色分配字符代号
  b) 在坐标网格模板上规划每个像素的位置
  c) 遵循分层思路：先轮廓(K) → 再底色(R) → 再高光(W) → 最后阴影(S)

  字符代号示例：
    K=#000000（轮廓）, R=#E74C3C（底色）, W=#FFFFFF（高光）
    S=#C0392B（阴影）, .=transparent（透明背景）

第3步：用 draw_from_grid 一次性平涂绘制（★核心步骤★）
  将规划好的网格字符串传入 draw_from_grid 工具。
  一次调用即可绘制整幅图——不要用 draw_rect/draw_pixel 逐个画！

  示例调用：
    draw_from_grid(
      grid=".....KKKKKK...../....KRRRRRRK..../...KRRWWWWRRK.../...KRWWWWWWRK.../...",
      colormap="K=#000000,R=#E74C3C,W=#FFFFFF,S=#F5DEB3,.=transparent"
    )

  网格规划要点（遵循像素艺术规范）：
  - 斜线保持 45 度角，阶梯均匀（如 1-2-2-1 排列），避免锯齿
  - 轮廓线宽度统一为 1 像素，保持连续不断裂
  - 光源默认设在左上方：高光在左上侧，阴影在右下侧
  - 主体居中，留出 1-2 像素边距

第4步：预览检查（必须执行！）
  调用 get_canvas_preview（scale=4 放大4倍便于观察）
  检查要点：
  - 剪影是否辨识？（纯黑色也能认出是什么吗？）
  - 轮廓是否连续清晰？
  - 颜色对比是否足够？
  - 是否有像素错位或遗漏？

第5步：修正与迭代（至少2轮！）
  根据预览分析结果修正：
  - 形状不对 → clear_region 清除问题区域，重新 draw_from_grid
  - 缺少描边 → 调用 add_outline 自动添加轮廓
  - 对称修正 → 用 mirror_half 镜像复制（只画一半再镜像）
  - 颜色调整 → 用 replace_color 替换不满意的颜色
  - 细节微调 → 用 draw_pixel 修正 1-3 个像素（仅少量修正）
  修正后再次 get_canvas_preview 验证

第6步：保存
  调用 save_sprite 保存最终结果

══════════════════════════════════════════
坐标网格规划模板（{size}）：
══════════════════════════════════════════
{grid_example}

══════════════════════════════════════════
推荐配色方案：
══════════════════════════════════════════
{palette_suggestion}

配色规范：
- 使用 4-8 种颜色（专业像素艺术的核心约束）
- 每种主色必须配套阴影色（RGB×0.7）和高光色（RGB×1.3，上限255）
- 轮廓色统一使用最深色（通常 #000000）
- 使用 indexed 色彩模式（create_sprite 默认 rgb，可改为 indexed）

══════════════════════════════════════════
工具使用优先级：
══════════════════════════════════════════
  1. draw_from_grid  ← 绘制完整精灵（首选，1次调用）
  2. add_outline     ← 自动描边（后期处理）
  3. mirror_half     ← 对称镜像（减少工作量）
  4. draw_pixel      ← 仅修正1-3个像素
  5. draw_rect       ← 仅画背景大色块
  6. draw_line       ← 仅画结构线（剑、法杖）
"""

    @mcp.prompt
    def iterate_sprite_prompt(session_id: str, feedback: str) -> str:
        """生成迭代审查引导消息。

        Args:
            session_id: 当前会话 ID
            feedback: 对当前画布的反馈意见
        """
        return f"""请根据以下反馈修改精灵画布（会话 ID: {session_id}）。

反馈意见：{feedback}

迭代修正工作流程：
1. 调用 get_canvas_preview（scale=4）查看当前画布状态
2. 仔细分析图片，对照反馈意见定位需要修改的区域
3. 根据问题类型选择修正方式：
   - 大面积修改 → clear_region 清除后用 draw_from_grid 重画
   - 缺少描边 → 调用 add_outline 自动添加轮廓
   - 颜色不满意 → 调用 replace_color 替换颜色
   - 不对称 → 用 mirror_half 镜像修正
   - 少量像素错误 → 用 draw_pixel 修正（仅1-3个）
4. 再次调用 get_canvas_preview 验证修正效果
5. 如果不满意，重复步骤 3-4（至少迭代2轮）
6. 满意后调用 save_sprite 保存

迭代要点：
- 每次只改一处，改完预览验证后再改下一处
- 大面积修改必须先 clear_region 再重画，避免颜色叠加
"""

    @mcp.prompt
    def create_animation_prompt(
        description: str,
        frame_count: int = 4,
        fps: int = 8,
        size: str = "32x32",
    ) -> str:
        """生成动画创作引导消息。

        Args:
            description: 动画描述（如"行走循环"、"闪烁星星"）
            frame_count: 帧数（默认4帧）
            fps: 每秒帧数（默认8fps，即每帧0.125秒）
            size: 画布尺寸，如 32x32
        """
        duration = round(1.0 / fps, 4)
        return f"""请使用 Aseprite MCP 工具创建一个动画：{description}

动画参数：{frame_count} 帧，{fps} fps（每帧 {duration} 秒），画布 {size}

══════════════════════════════════════════
专业动画工作流程：
══════════════════════════════════════════

第1步：创建画布并绘制关键帧
  1. 调用 create_sprite 创建 {size} 画布
  2. 用 draw_from_grid 绘制第1帧（关键帧——最标准的姿势）
  3. 调用 get_canvas_preview 预览，确保造型满意
  4. 如不满意，clear_region + draw_from_grid 重画

第2步：绘制其他关键帧
  专业动画师先画关键帧（最极端姿势），再补中间帧：
  - 行走循环的关键帧：站立 → 迈左腿最远 → 站立 → 迈右腿最远
  - 每个关键帧用 draw_from_grid 一次性绘制

  对每一帧：
  1. 调用 add_frame（content="copy"）复制上一帧作为基础
  2. 用 clear_region 清除需要变化的部分
  3. 用 draw_from_grid 绘制本帧变化内容（只画变化部分即可）
  4. 调用 get_canvas_preview 预览检查

第3步：设置帧时长
  对每一帧调用 set_frame_duration 设置时长为 {duration} 秒

第4步：逐帧检查动画连贯性
  对每一帧调用 get_canvas_preview 检查：
  - 相邻帧变化是否太大或太小？（行走动画每帧位移 1-2 像素）
  - 是否有抖动（不该动的像素在跳动）？
  - 动作是否流畅？

第5步：导出与保存
  1. 可选：调用 add_tag 创建动画标签（如"Walk"），设置播放方向
  2. 调用 export_gif 导出 GIF 动画
  3. 调用 save_sprite 保存

══════════════════════════════════════════
理想调用次数（{frame_count} 帧，调用优化基准）：
══════════════════════════════════════════
  create_sprite(1) → draw_animation_frames(1) → apply_timing_preset(1)
  → check_canvas_standards(1) → [pass]export_gif(1) = 5 次
禁止：逐帧循环 draw_from_grid / 逐帧 set_frame_duration / 每步必 preview

动画规范：
- 每帧只做小幅修改（1-3像素位移），保持动作连贯
- 先画关键帧（最极端姿势），再补中间帧
- 对称动作可以用 mirror_half 减少工作量
- draw_from_grid 的 offset 参数可在帧间做微调
"""

    @mcp.prompt
    def multi_layer_prompt(
        description: str,
        layer_count: int = 3,
        size: str = "32x32",
    ) -> str:
        """生成多图层创作引导消息。

        Args:
            description: 创作描述（如"带背景的角色场景"）
            layer_count: 图层数量（默认3层：背景、主体、前景）
            size: 画布尺寸，如 32x32
        """
        return f"""请使用 Aseprite MCP 工具创建一个多图层作品：{description}

图层数量：{layer_count} 层，画布 {size}

══════════════════════════════════════════
专业多图层工作流程：
══════════════════════════════════════════

第1步：创建画布和图层
  1. 调用 create_sprite 创建 {size} 画布（第1层为默认背景层）
  2. 调用 add_layer 创建额外图层（共 {layer_count} 层）
  3. 调用 get_layer_info 确认图层结构

第2步：逐层绘制（从背景到前景）
  背景层（layer=1）：
  - 用 draw_from_grid 绘制背景（大色块为主，细节少）
  - 背景颜色偏冷偏暗，不抢主体

  主体层（layer=2）：
  - 用 draw_from_grid 绘制主要角色（视觉焦点）
  - 细节最多，颜色最丰富
  - 画完后调用 add_outline 自动描边

  前景层（layer=3，如有）：
  - 绘制前景细节（如草地、雾气、光效）
  - 可用 set_layer_properties 设半透明（opacity=128）

  每层画完后调用 get_canvas_preview 检查

第3步：调整图层混合
  使用 set_layer_properties 调整：
  - 不透明度：0-255（128=半透明）
  - 混合模式：normal, multiply, screen, overlay, darken, lighten
  建议尝试：
    - 阴影层用 multiply 让阴影更自然
    - 光效层用 screen 或 lighten 增加光感

第4步：整体预览与迭代
  1. 调用 get_canvas_preview 预览整体效果
  2. 如需修改特定图层，绘制时指定 layer 参数
  3. 至少迭代2轮：检查各层是否协调，主体是否突出

第5步：保存
  调用 save_sprite 保存
"""

    @mcp.prompt
    def create_tileset_prompt(
        description: str, tile_size: str = "16x16", cols: int = 6, rows: int = 3
    ) -> str:
        """生成瓦片集创作引导消息。

        Args:
            description: 瓦片集描述（如"草地与泥土过渡瓦片"）
            tile_size: 单块瓦片尺寸（如 16x16）
            cols: 横向瓦片数
            rows: 纵向瓦片数
        """
        return f"""请使用 Aseprite MCP 工具创建瓦片集：{description}

参数：{tile_size} 瓦片，{cols}x{rows} 布局

══════════════════════════════════════════
专业 Tileset 工作流程（docs §8）：
══════════════════════════════════════════

第1步：创建瓦片画布
  调用 create_tileset_canvas（tile_size={tile_size.split('x')[0]}, cols={cols}, rows={rows}）
  网格自动设为瓦片尺寸，清晰看到每块边界，避免越界污染相邻瓦片。

第2步：读取瓦片模板（可选参考）
  调用 aseprite://tileset/templates 查看可用模板
  调用 aseprite://tileset/templates/{{name}} 取具体 grid/colormap

第3步：绘制瓦片
  用 draw_from_grid 绘制单块瓦片（用 offset_x/offset_y 定位到瓦片格）
  完整一套需：中心块、边缘块、角块、过渡瓦片、装饰块（docs §8.3）

第4步：检查接缝（必须执行！）
  调用 export_tiled_preview（repeat=2）导出 2x2 拼接预览
  检查拼接处是否有可见接缝：
  - 边缘像素是否与相邻瓦片匹配？
  - 是否有 1 像素偏移？
  有接缝 → 修正边缘像素 → 再次 export_tiled_preview 验证

第5步：保存
  调用 save_sprite 保存

══════════════════════════════════════════
理想调用次数（docs §8 工作流）：
══════════════════════════════════════════
  create_tileset_canvas(1) → draw_from_grid(N块) → export_tiled_preview(1)
  → [修正] → export_tiled_preview(1) → save_sprite(1)
禁止：逐像素绘制瓦片、跳过接缝检查
"""


# ══════════════════════════════════════════
# 坐标网格模板
# ══════════════════════════════════════════

_GRID_16X16_TEMPLATE = """```
    0123456789012345
  0 ................
  1 ................
  2 .....KKKKKK.....
  3 ....KRRRRRRK....
  4 ...KRRWWWWRRK...
  5 ...KRWWWWWWRK...
  6 ...KRRWWWWRRK...
  7 ....KRRRRRRK....
  8 .....KKKKKK.....
  9 .....KSSSSK.....
 10 .....KSSSSK.....
 11 .....KKKKKK.....
 12 ................
 13 ................
 14 ................
 15 ................
```
说明：K=轮廓, R=底色, W=高光, S=阴影, .=透明
注意斜线保持阶梯均匀（如轮廓的 45 度角部分）。
这是一个蘑菇的示例布局。绘制时替换为你需要的字符和颜色。"""

_GRID_32X32_TEMPLATE = """```
    01234567890123456789012345678901
  0 ................................
  1 ................................
  2 ..........KKKKKKKK..............
  3 ........KKRRRRRRRRKK............
  4 .......KRRRRRRRRRRRRK...........
  5 ......KRRRWWWWWWWWRRRK..........
  6 .....KRRWWWWWWWWWWWWRRK.........
  7 .....KRRWWWWWWWWWWWWRRK.........
  8 ......KRRWWWWWWWWWWRRK..........
  9 .......KRRRRRRRRRRRRK...........
 10 ........KKRRRRRRRRKK............
 11 ..........KKKKKKKK..............
 12 ............KSSK................
 13 ...........KSSSSK...............
 14 ...........KSSSSK...............
 15 ...........KSSSSK...............
 16 ..........KSSSSSSK..............
 17 ..........KSSSSSSK..............
 18 .........KSSSSSSSSK.............
 19 ................................
```
说明：K=轮廓, R=底色, W=高光, S=阴影, .=透明
注意光源在左上方——高光(W)在左上，阴影(S)在右下。
这是角色示例布局。绘制时替换为你需要的字符和颜色。"""


# ══════════════════════════════════════════
# 配色方案库（遵循有限调色板规范）
# ══════════════════════════════════════════

_PALETTE_SUGGESTIONS = {
    "character_16": """角色配色（16x16，5色）：
  K=#000000  轮廓（黑色）
  S=#8B4513  主体（棕色）
  L=#D2691E  亮部（浅棕）
  W=#FFF8DC  高光（米白）
  E=#FFFFFF  眼睛（白色）

蘑菇配色（5色）：
  K=#000000  轮廓
  R=#E74C3C  红色帽盖
  S=#C0392B  红色阴影
  W=#FFFFFF  白色斑点
  T=#F5DEB3  茎部（麦色）

宝石配色（4色）：
  K=#000000  轮廓
  B=#29ADFF  蓝色主体
  D=#1D7BB3  深蓝阴影
  W=#A9E2FF  浅蓝高光""",

    "character_32": """角色配色（32x32，8色）：
  K=#000000  轮廓（黑色）
  H=#8B4513  头发（棕色）
  S=#D2691E  皮肤（浅棕）
  L=#F5DEB3  皮肤高光（麦色）
  C=#2C3E50  衣服（深蓝灰）
  E=#3498DB  衣服亮部（蓝色）
  P=#E74C3C  装饰（红色）
  W=#FFFFFF  眼睛/高光（白色）

树木配色（6色）：
  K=#000000  轮廓
  T=#2D5016  树冠深绿
  G=#4A7C20  树冠中绿
  L=#6BAA33  树冠亮绿
  B=#8B4513  树干（棕色）
  S=#5C3317  树干阴影（深棕）

宝箱配色（7色）：
  K=#000000  轮廓
  W=#8B4513  木箱主体（棕色）
  S=#5C3317  木箱阴影（深棕）
  G=#DAA520  金边（金色）
  L=#FFD700  金边高光（亮金）
  R=#E74C3C  红宝石（红色）
  Y=#FFEC27  宝石高光（黄色）""",

    "icon": """图标配色（4-5色）：
  心形：K=#000000, R=#E74C3C, S=#C0392B, W=#FFB3B3, .=transparent
  星星：K=#000000, Y=#FFEC27, O=#FFA300, W=#FFF8DC, .=transparent
  剑：  K=#000000, B=#C0C0C0, D=#808080, G=#8B4513, W=#FFFFFF, .=transparent
  盾：  K=#000000, B=#2980B9, D=#1B4F72, G=#DAA520, W=#FFFFFF, .=transparent
  药水：K=#000000, R=#E74C3C, S=#C0392B, W=#FFB3B3, G=#2ECC71, .=transparent""",
}
