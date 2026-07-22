"""MCP Prompts：预定义工作流模板。

提供精灵创作引导、迭代审查引导、动画创作引导和多图层工作流引导。
所有 prompt 均包含坐标网格规划模板、配色方案和分步策略，以提升生成质量。
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
推荐工作流程（质量优先）：
══════════════════════════════════════════

第1步：创建画布
  调用 create_sprite 创建 {size} 画布

第2步：规划像素布局（在脑中或文本中完成）
  先用文本网格规划每个像素的位置和颜色，参考下方网格模板。
  为每种颜色分配一个字符代号，例如：
    K=#000000（黑色轮廓）, R=#E74C3C（红色主体）, W=#FFFFFF（白色高光）
    S=#C0392B（暗红色阴影）, .=transparent（透明背景）

第3步：用 draw_from_grid 一次性绘制（推荐！）
  将规划好的网格字符串传入 draw_from_grid 工具。
  这是最高效的方式：一次调用即可绘制整幅图。
  示例：
    grid = "KKKKKKKKKKKKKKKK/KRRRRRRRRRRRRRRK/KRRWWWWWWWWWWRRK/..."
    colormap = "K=#000000,R=#E74C3C,W=#FFFFFF,.=transparent"

  备选方式（如果网格太复杂）：
    a) 用 draw_rect 填充大色块底色
    b) 用 draw_line 画主要轮廓线
    c) 用 draw_pixel 逐个补充细节

第4步：预览并分析
  调用 get_canvas_preview（scale=4 放大4倍便于观察）
  仔细分析图片，检查：
    - 轮廓是否清晰？形状是否辨识？
    - 颜色对比是否足够？是否需要加深阴影？
    - 是否有像素错位或遗漏？

第5步：修正与迭代（至少迭代2轮！）
  根据预览分析结果修正：
    - 形状不对 → 用 clear_region 清除问题区域后重画
    - 缺少描边 → 调用 add_outline 自动添加黑色轮廓
    - 需要对称 → 用 mirror_half 镜像复制
    - 颜色调整 → 用 replace_color 替换不满意的颜色
  修正后再次调用 get_canvas_preview 验证

第6步：保存最终结果
  调用 save_sprite 保存

══════════════════════════════════════════
坐标网格规划模板（{size}）：
══════════════════════════════════════════
{grid_example}

规划要点：
- 先确定主体在网格中的居中位置
- 从外轮廓开始规划，再填充内部颜色
- 阴影画在光源对侧，高光画在光源同侧
- 保持轮廓连续不断裂

══════════════════════════════════════════
推荐配色方案：
══════════════════════════════════════════
{palette_suggestion}

配色要点：
- 使用 4-8 种颜色，不要太多
- 每种主色需要配套的阴影色（暗30%）和高光色（亮30%）
- 轮廓色统一使用最深色（通常为黑色 #000000）

══════════════════════════════════════════
像素艺术技巧：
══════════════════════════════════════════
- {size} 适合简单图标，32x32 适合角色
- 先画轮廓再填充底色，最后加高光阴影
- 像素之间不要留空隙
- 避免曲线锯齿：斜线保持45度角，阶梯均匀
- 对称图形只画一半，用 mirror_half 镜像
- 画完后用 add_outline 自动描边增强轮廓
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
   - 形状不对 → 用 clear_region 清除问题区域，再用 draw_from_grid 或 draw_pixel 重画
   - 缺少描边 → 调用 add_outline 自动添加轮廓
   - 颜色不满意 → 调用 replace_color 替换颜色
   - 不对称 → 用 mirror_half 镜像修正
   - 细节缺失 → 用 draw_pixel 逐个补充
4. 再次调用 get_canvas_preview 验证修正效果
5. 如果不满意，重复步骤 3-4（至少迭代2轮）
6. 满意后调用 save_sprite 保存

迭代要点：
- 每次只改一处，改完预览验证后再改下一处
- 修改时先清除再重画，避免颜色叠加
- 注意修改后是否破坏了整体平衡
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
动画创作工作流程：
══════════════════════════════════════════

第1步：创建画布并绘制第1帧
  1. 调用 create_sprite 创建 {size} 画布
  2. 用 draw_from_grid 绘制第1帧（推荐！一次性完成）
  3. 调用 get_canvas_preview 预览第1帧，确保造型满意
  4. 如不满意，用 clear_region + draw_from_grid 修正

第2步：创建后续帧
  对每一帧（第2帧到第{frame_count}帧）：
  1. 调用 add_frame（content="copy"）复制上一帧
  2. 用 clear_region 清除需要变化的部分
  3. 用 draw_from_grid 或 draw_pixel 绘制本帧变化内容
  4. 调用 get_canvas_preview 预览检查

第3步：设置帧时长
  对每一帧调用 set_frame_duration 设置时长为 {duration} 秒

第4步：逐帧检查动画效果
  对每一帧调用 get_canvas_preview 检查：
  - 动作是否连贯？相邻帧变化是否太大或太小？
  - 是否有抖动（像素无规律跳动）？
  - 如有问题，用 clear_region + draw_from_grid 修正

第5步：导出与保存
  1. 可选：调用 add_tag 创建动画标签（如"Walk"），设置播放方向
  2. 调用 export_gif 导出 GIF 动画
  3. 调用 save_sprite 保存

══════════════════════════════════════════
动画技巧：
══════════════════════════════════════════
- 每帧只做小幅修改（1-3像素位移），保持动作连贯
- 行走循环：腿和手臂交替前后摆动，身体微微上下起伏
- 闪烁/呼吸：缩放或明暗交替变化
- 使用 mirror_half 对称帧减少工作量
- 可以用 move_cel 在不同图层间移动内容
- 先画关键帧（最极端的姿势），再补中间帧
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
多图层工作流程：
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
  - 用 draw_from_grid 绘制主要角色或物体（视觉焦点）
  - 细节最多，颜色最丰富
  - 画完后调用 add_outline 自动描边

  前景层（layer=3，如有）：
  - 绘制前景细节（如草地、雾气、光效）
  - 可用 set_layer_properties 设半透明（opacity=128）

  每层画完后调用 get_canvas_preview 检查

第3步：调整图层混合
  可选：使用 set_layer_properties 调整：
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

技巧：
- 背景层使用较大色块，细节少
- 主体层是视觉焦点，细节最多
- 前景层可设半透明（opacity=128）增加层次感
- draw_from_grid 可指定 layer 参数分层绘制
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
说明：K=轮廓, R=红色主体, W=白色高光, S=阴影, .=透明
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
 20 ................................
 21 ................................
 22 ................................
 23 ................................
 24 ................................
 25 ................................
 26 ................................
 27 ................................
 28 ................................
 29 ................................
 30 ................................
 31 ................................
```
说明：K=轮廓, R=红色主体, W=白色高光, S=阴影, .=透明
这是一个角色的示例布局。绘制时替换为你需要的字符和颜色。"""


# ══════════════════════════════════════════
# 配色方案库
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
