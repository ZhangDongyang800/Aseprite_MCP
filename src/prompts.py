"""MCP Prompts：预定义工作流模板。

基于专业像素艺术工作流设计：草图 → 线稿 → 平涂底色 → 阴影/高光 → 描边 → 导出。
参考 Aseprite 官方文档和专业游戏美术实践。

注意：工具面已经收敛到 apply_operations / inspect / run_lua 三个工具。
这里写的每一个 op 名都必须真的在 op 注册表里，否则客户端照着调就是一个
死循环 —— tools/ 里的旧工具早已删除。
"""


def _parse_size(size: str, default: int = 16) -> tuple:
    """把 "16x16" 解析成 (16, 16)，解析不了就用 default 兜底。

    prompt 只是引导文案，不该因为一个奇怪的 size 参数就整个渲染失败。
    """
    try:
        w, h = str(size).lower().split("x", 1)
        return int(w), int(h)
    except (AttributeError, TypeError, ValueError):
        return default, default


# 三个工具的用法。每个 prompt 都重复这段，因为 prompt 是独立发给 AI 的，
# 拿不到彼此的上下文。
_TOOL_SURFACE = """══════════════════════════════════════════
工具面：只有三个工具，全部绘图都从这里进
══════════════════════════════════════════

apply_operations(ops, session_id=None, atomic=True, dry_run=False,
                 confirmed=False, verbose=False)
  唯一的变更入口。ops 是一个列表，每项形如 {"op": "<op名>", ...该 op 的参数}。
  整批在一个事务里跑：atomic=true（默认）任一 op 失败即整体回滚，不留半成品。
  - 省略 session_id 时，只要首个 op 是 create_sprite 或 open_sprite，
    服务器会自动建会话并注入文件路径；返回值里的 session_id 就是后续要用的。
  - dry_run=true 只校验并返回执行计划，不落笔。大批量前空跑一次很便宜。
  - verbose=true 回显完整计划；否则 op_results 只给服务器才知道的新信息。

inspect(session_id, scale=4, view="composite", frame=1)
  只读预览，永不改动文档。返回放大图 + 量化指标：color_count（用了多少色）、
  palette（实际用色）、bbox（内容包围盒）、coverage（覆盖率）、width/height。
  动画用 frame（1 起）看指定帧，越界会夹到有效范围。

run_lua(session_id, code, unsafe=False, confirmed=False)
  逃逸舱，跑任意 Aseprite Lua。必须 unsafe=true 且 confirmed=true，两个都要。
  只在 op 词汇确实做不到时用 —— 目前主要是图层组、混合模式、区域变换。
  能用 op 表达的，不要用它。
  CLI 模式下 snippet 失败会回滚 .ase，成功则留一份 undo 备份。

── 破坏性 op 的确认门闩 ──
  clear_canvas（清空当前层/帧，layer=0 清整帧所有层）、delete_layer 和
  close_session（销毁会话）是破坏性 op。
  批量里只要出现其中一个，没带 confirmed=true 就整批拒绝，什么都不会发生。
  → 重画或收工销毁时，apply_operations 要显式传 confirmed=true。

── op 词汇表（完整，就这些）──
  会话  create_sprite(width, height, color_mode) / open_sprite(path) /
        save_sprite(path) / close_session /
        add_layer(name, opacity) / set_layer(layer, name, opacity, visible) /
        delete_layer(layer) / set_palette(colors)
  绘制  draw_pixel(x, y, color) / draw_rect(x, y, width, height, color, filled) /
        draw_line(x1, y1, x2, y2, color) /
        draw_ellipse(cx, cy, rx, ry, color, filled) /
        fill_region(x, y, color) / paint_grid(path, x, y) / clear_canvas(layer, frame)
  结构  add_frames(count, duration, duplicate) / set_durations(durations) /
        add_tag(name, from_frame, to_frame)
  输出  export(format="png"|"gif"|"sheet"|"frames", output, scale=1,
         frame, tag, layout, columns, padding) —— 只写文件，不改文档
  历史  undo / redo（必须单独成批，不能和其他 op 混在一批里）
  所有绘制类 op 都接受 layer（1 起）和 frame（1 起），默认都是 1。
  indexed 文档先 set_palette 再画；索引 0 是透明索引。

── 两件必须知道的事 ──
  1. 新建的精灵只有 1 层 1 帧。帧不够用 add_frames 补；图层用 add_layer 建，
     新层追加在顶部，layer 参数用 1 起的层号。clear_canvas(layer=0) 清整帧所有层。
  2. paint_grid 的 path 必须指向一个 Lua 数据文件，返回
     {palette = {字符="#RRGGBB", ...}, rows = {"...", ...}}。
     Aseprite 这版 Lua 没有 loadstring，JSON 读不出 table，所以只能用这个格式。
     文件在服务器工作目录内可直接跑；指向目录外需要 confirmed=true。

── paint_grid 网格文件长这样 ──
    -- mushroom.lua
    return {
      palette = { K = "#000000", R = "#E74C3C", W = "#FFFFFF", S = "#F5DEB3" },
      rows = {
        "................",
        ".....KKKKKK.....",
        "....KRRRRRRK....",
        "....KRRWWWWRK...",
      },
    }
  "." 表示该像素不画。网格里出现 palette 没有的字符、或画到画布外，
  都会让整批报错回滚 —— 先 dry_run=true 空跑确认放得下，能省一整轮返工。"""


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

        width, height = _parse_size(size)

        return f"""请使用 Aseprite MCP 绘制一个精灵：{description}

{_TOOL_SURFACE}

══════════════════════════════════════════
专业像素艺术工作流程（草图 → 线稿 → 平涂 → 阴影 → 描边）：
══════════════════════════════════════════

第1步：规划像素布局（先规划，再绘制）
  在绘制前先用文本网格规划整个精灵的像素布局。
  这是专业像素艺术的核心 —— 先规划再绘制，而不是边画边想。

  规划方法：
  a) 先确定配色方案（从下方参考中选择或自定义），为每种颜色分配字符代号
  b) 在坐标网格模板上规划每个像素的位置
  c) 遵循分层思路：先轮廓(K) → 再底色(R) → 再高光(W) → 最后阴影(S)

  字符代号示例：
    K=#000000（轮廓）, R=#E74C3C（底色）, W=#FFFFFF（高光）
    S=#C0392B（阴影）, .=不画（透明背景）

第2步：整幅图一次画完，不要逐像素
  规划好的网格写成一个 Lua 文件（格式见上），然后一次批量完成建画布 + 上色：

    apply_operations(ops=[
      {{"op": "create_sprite", "width": {width}, "height": {height}}},
      {{"op": "paint_grid", "path": "<上面那个 .lua 文件的绝对路径>"}},
    ])

  paint_grid 是画完整幅图的首选，一次调用搞定 —— 不要用
  draw_pixel 逐个画，也不要一个像素一个 op。

  网格规划要点（遵循像素艺术规范）：
  - 斜线保持 45 度角，阶梯均匀（如 1-2-2-1 排列），避免锯齿
  - 轮廓线宽度统一为 1 像素，保持连续不断裂
  - 描边直接写进网格（K 字符），没有单独的描边 op
  - 对称图形在规划时就左右对称地写，不要指望事后镜像
  - 光源默认设在左上方：高光在左上侧，阴影在右下侧
  - 主体居中，留出 1-2 像素边距

第3步：inspect 预览检查（必须执行！）
  inspect(session_id, scale=4) —— 放大 4 倍便于观察，同时给出量化指标。
  检查要点：
  - 剪影是否辨识？（纯黑色也能认出是什么吗？）
  - 轮廓是否连续清晰？
  - color_count 是否在 4-8 色的节制范围内？palette 里有没有你压根没打算用的颜色？
  - bbox 是否居中、coverage 是否合理（太低说明主体画得太小或偏了）？
  - 是否有像素错位或遗漏？

第4步：修正与迭代（至少2轮！）
  - 形状或配色整体不对 → 用 {{"op": "clear_canvas"}} 整层清空后重新 paint_grid
    （clear_canvas 是破坏性 op，批量里必须带 confirmed=true）
  - 只差 1-3 个像素 → 用 draw_pixel 定点修正，不要为了两个像素整层重画
  - 大片同色区域 → draw_rect（画色块）或 fill_region（填已有区域）
  - 想换配色 → 改网格文件里的 palette 色值再 paint_grid 重画，比逐像素换色稳
  每轮修正后再次 inspect 验证。

第5步：保存
  apply_operations(ops=[{{"op": "save_sprite"}}]) —— 不给 path 就落回会话的 .ase。
  收工要销毁会话时 close_session 也是破坏性 op，同样需要 confirmed=true。

第6步：导出交付物（需要文件时）
  apply_operations(ops=[{{"op": "export", "format": "png",
                         "output": "<绝对路径>.png", "scale": 4}}])
  - 单帧 png 用 frame=N；多帧精灵表用 format="sheet"；动画用 format="gif"；
    逐帧参考图用 format="frames"（会写成 name1.png..nameN.png）。
  - export 只写文件、不改文档，不需要 confirmed；产物路径在返回的 artifacts 里。
  - 输出目录必须已存在；格式和扩展名必须匹配（png/sheet/frames → .png，gif → .gif）。

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
- create_sprite 的 color_mode 默认 rgb，可改为 indexed；indexed 必须先 set_palette，
  且索引 0 是透明索引（画在索引 1 及以后）

══════════════════════════════════════════
op 使用优先级：
══════════════════════════════════════════
  1. paint_grid    ← 整幅图一次画完（首选，1 次调用）
  2. draw_pixel    ← 仅修正1-3个像素
  3. draw_rect     ← 画背景大色块 / 结构块
  4. fill_region   ← 已有区域的同色填充
  5. export        ← 交付 PNG/GIF/精灵表，不改文档（需要文件时最后调用）
  6. clear_canvas  ← 推倒重来（破坏性，需 confirmed=true）
  7. run_lua       ← 仅限图层组/混合模式/区域变换等 op 做不到的事（需 unsafe + confirmed）
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

{_TOOL_SURFACE}

迭代修正工作流程：
1. inspect(session_id="{session_id}", scale=4) —— 先看清现状，别凭记忆改
2. 仔细分析图片，对照反馈意见定位需要修改的区域
3. 根据问题类型选择修正方式（都在 apply_operations 里）：
   - 大面积要改 → {{"op": "clear_canvas", "layer": L}} 清除后重新 paint_grid
     （clear_canvas 是破坏性 op，批量必须带 confirmed=true）
   - 只差1-3个像素 → draw_pixel 定点修正（最省事，也最不容易改坏别处）
   - 颜色不满意 → 改网格文件的 palette 再 paint_grid 重画，比逐像素换色稳
   - 缺少描边 → 把轮廓色写进网格规划，用 paint_grid 重画
   - 不对称 → 在网格规划里就左右对称地写，没有事后镜像的 op
4. 再次 inspect 验证修正效果
5. 如果不满意，重复步骤 3-4（至少迭代2轮）
6. 满意后 apply_operations(ops=[{{"op": "save_sprite"}}])

迭代要点：
- 每次只改一处，改完 inspect 验证后再改下一处
- 大面积修改必须先 clear_canvas 再重画，避免新旧颜色叠加打架
- 连续几轮没进展 → 先看 inspect 的量化指标（color_count / bbox / coverage），
  用数据定位问题，而不是继续盲改
- 走错了一步 → apply_operations(ops=[{{"op": "undo"}}]) 撤销（undo 必须单独成批）
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
        width, height = _parse_size(size, default=32)
        extra_frames = max(frame_count - 1, 0)

        return f"""请使用 Aseprite MCP 创建一个动画：{description}

动画参数：{frame_count} 帧，{fps} fps（每帧 {duration} 秒），画布 {size}

{_TOOL_SURFACE}

══════════════════════════════════════════
专业动画工作流程：
══════════════════════════════════════════

第1步：建画布并绘制第1帧
  关键帧 = 最标准的姿势。一次批量做完建画布 + 上色：

    apply_operations(ops=[
      {{"op": "create_sprite", "width": {width}, "height": {height}}},
      {{"op": "paint_grid", "path": "<第1帧网格文件>", "frame": 1}},
    ])

  然后 inspect 确认造型满意。不满意就 clear_canvas（破坏性 op，
  批量带 confirmed=true）重来。

第2步：一次加满所有帧
  add_frames 是唯一加帧的 op，一次 count 补齐，别循环加 1 帧：

    apply_operations(ops=[
      {{"op": "add_frames", "count": {extra_frames}, "duration": {duration}, "duplicate": true}},
    ])

  duplicate=true 让新帧带上上一帧的内容作为起点 —— 空白帧从头重画
  是帧间脱节的头号来源。duration 一并给上，省掉后面逐帧设。

第3步：逐帧只改变化的部分
  所有绘制类 op 都吃 frame 参数（1 起）。核心原则：
  **帧 N+1 = 帧 N + 增量**

  - 行走循环的关键帧：站立 → 迈左腿最远 → 站立 → 迈右腿最远
  - 每帧只重画真正会动的像素（1-3 像素位移），静态部分一个都别碰
  - 用 paint_grid 的 x/y 指定变化区域的左上角，只重画那块
  - 帧间的对照就是拿 inspect 的 frame 参数一帧一帧看

  同一批里可以放多个 op（都是对第 F 帧的修改），一次调用提交。

第4步：逐帧检查动画连贯性
  inspect(session_id, frame=F, scale=4) 逐帧检查：
  - 相邻帧变化是否太大或太小？（行走动画每帧位移 1-2 像素）
  - 有没有抖动（不该动的像素在跳动）？
  - 动作是否流畅？

  inspect 是只读的，随时可以看。一次看不全就多调几次 frame。
  量化指标也能看：bbox 应该逐帧平滑移动，不该忽大忽小；
  coverage 在一个循环里应当大致稳定。

第5步：设帧时长、打标签、保存
  - 不要所有帧用同一个时长（蓄力短、命中长是专业做法）：
    查 aseprite://timing/presets 拿建议值，然后
    apply_operations(ops=[{{"op": "set_durations", "durations": [...]}}]) 一次设完
    （单位是秒，每个值满足 0 < d <= 60）
  - apply_operations(ops=[{{"op": "add_tag", "name": "Walk", "from_frame": 1,
    "to_frame": {frame_count}}}]) 给帧区间命名，之后按标签播放（可选）
  - apply_operations(ops=[{{"op": "save_sprite"}}])

══════════════════════════════════════════
理想调用次数（{frame_count} 帧，调用优化基准）：
══════════════════════════════════════════
  create_sprite(1) + paint_grid(1) + add_frames(1) + [每帧 paint_grid 1 次]
  → set_durations(1) + add_tag(1) + save_sprite(1) + inspect(1~2)
  禁止：逐帧循环 add_frames / 逐帧单独调 set_durations / 每帧都 inspect
        / 每帧整幅空白重画

动画规范：
- 每帧只做小幅修改（1-3像素位移），保持动作连贯
- 先画关键帧（最极端姿势），再补中间帧
- add_frames(duplicate=true) 让每帧从上一帧继承，别从空白起步
- 对称动作（如走路摆臂）在网格规划里就左右对称地写
"""

    @mcp.prompt
    def animation_consistency_prompt(
        description: str,
        frame_count: int = 4,
        fps: int = 8,
        size: str = "32x32",
    ) -> str:
        """生成动画一致性工作流引导（帧继承 + 增量编辑 + 逐帧验证）。

        解决 AI 动画最常见的帧间脱节问题：每帧必须基于上一帧做增量，
        静态部分靠 add_frames(duplicate=true) 继承，动态部分只局部重画。

        Args:
            description: 动画描述（如"行走循环"、"挥剑攻击"）
            frame_count: 帧数（默认4帧）
            fps: 每秒帧数（默认8fps）
            size: 画布尺寸，如 32x32
        """
        duration = round(1.0 / fps, 4)
        width, height = _parse_size(size, default=32)
        extra_frames = max(frame_count - 1, 0)

        return f"""请使用 Aseprite MCP 创建动画：{description}

动画参数：{frame_count} 帧，{fps} fps（每帧 {duration} 秒），画布 {size}

{_TOOL_SURFACE}

══════════════════════════════════════════
帧间一致性工作流（核心原则：帧 N+1 = 帧 N + 增量）
══════════════════════════════════════════

第1步：一次性把帧数铺好
  帧一致性从结构上保证，不靠事后补救。一次批量搞定建画布 + 第1帧 + 全部帧：

    apply_operations(ops=[
      {{"op": "create_sprite", "width": {width}, "height": {height}}},
      {{"op": "paint_grid", "path": "<第1帧关键姿势网格>", "frame": 1}},
      {{"op": "add_frames", "count": {extra_frames}, "duration": {duration},
        "duplicate": true}},
    ])

  duplicate=true 是这里的关键：静态像素从第 1 帧一路复制到全部帧，
  帧间零差异由构造保证，不是靠你记得重画。

第2步：逐帧做增量编辑（只改会动的那几像素）
  对每一帧（frame 从 1 起）：
  - 只重画变化的像素，幅度控制在 1-3 像素
  - 用 paint_grid 的 x/y 把改动精确摆到帧内对应位置，
    网格文件只写这块变化区域，不必重写整帧
  - 肢体平移 / 呼吸缩放这类整体位移，核心仍然是"只动会动的像素"
  - **绝对不要整帧空白重画！** 重画必失真，静态细节（高光、纹样、
    脸部特征）每一帧都会漂移

  同一帧的多个改动可以放在同一批 apply_operations 里提交。

第3步：逐帧验证差异（必须执行！）
  inspect(session_id, frame=F) 对每对相邻帧检查：
  - 变化的像素是不是集中在预期区域？（挥剑应集中在剑臂附近）
  - bbox 的移动是否平滑？不该忽大忽小
  - coverage 在一个循环里是否大致稳定？
  - 静态像素有没有跟着抖？（看前一帧再开后一帧比对）

  inspect 只读、便宜，多看几帧比画完再看一遍划算。
  想量化地确认哪几帧出了问题，就把相邻两帧各 inspect 一次对比 bbox。

第4步：设置帧时长与保存
  - 查 aseprite://timing/presets 拿建议时长（蓄力短、命中长），然后
    apply_operations(ops=[{{"op": "set_durations", "durations": [...]}}]) 一次设完
    （单位是秒，每个值满足 0 < d <= 60；不要全帧同一个值）
  - apply_operations(ops=[{{"op": "add_tag", "name": "Attack", "from_frame": 1,
    "to_frame": {frame_count}}}]) 给整条动画命名（可选）
  - apply_operations(ops=[{{"op": "save_sprite"}}])

══════════════════════════════════════════
分层说明（诚实版）：══════════════════════════════════════════
  "会动的部件单独建层"是好习惯。用 add_layer 建层（新层追加在顶部），
  再用 set_layer 调 name/opacity/visible；之后绘制 op 的 layer 参数才有意义。
  图层组、混合模式仍需 run_lua（unsafe=true 且 confirmed=true）。
  不分层也能用上面的增量编辑法做好帧一致性 —— 分层只是锦上添花。

══════════════════════════════════════════
op 使用优先级：
══════════════════════════════════════════
  1. add_frames(duplicate=true) ← 帧间继承，绝不空白重画
  2. paint_grid(x, y)          ← 仅局部修改时精确重画变化区域
  3. draw_pixel               ← 1-3 个像素的定点修正
  4. set_durations             ← 一次设完全部帧时长
  5. add_tag                   ← 给帧区间命名
禁止：每帧从空白开始重画 / 跳过 inspect 逐帧验证
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
        width, height = _parse_size(size, default=32)

        return f"""请使用 Aseprite MCP 创建一个多图层作品：{description}

图层数量：{layer_count} 层，画布 {size}

{_TOOL_SURFACE}

══════════════════════════════════════════
多图层现实（先看这段，免得白忙）
══════════════════════════════════════════
  新建的精灵只有第 1 层。layer_count > 1 时，先加层再逐层绘制：

    apply_operations(ops=[{{"op": "add_layer", "name": "主体"}}, ...])
    → 再用 paint_grid 的 layer 参数逐层画

  add_layer 返回新层的 1 起索引；新层追加在顶部。set_layer 调
  name/opacity/visible，delete_layer 删除（破坏性，需要 confirmed=true）。
  只有图层组或混合模式才需要 run_lua（unsafe=true 且 confirmed=true）。

══════════════════════════════════════════
多图层工作流程：
══════════════════════════════════════════

第1步：建画布，建层
  apply_operations(ops=[{{"op": "create_sprite", "width": {width},
                        "height": {height}}}])
  用 set_layer 把第 1 层改成背景层，再用 add_layer 加出主体层、前景层。
  新层追加在顶部；add_layer 返回 1 起索引。

  注意：层号是 1 起的（Aseprite 惯例，越大越靠上），
  绘制 op 的 layer 参数直接用这个层号。

第2步：逐层绘制（从背景到前景）
  每层各写一份网格文件（背景层可以复用同一份网格 + 不同 x/y），
  用 paint_grid 的 layer 参数指定画到哪一层：

    apply_operations(ops=[
      {{"op": "paint_grid", "path": "<背景网格>", "layer": 1}},
      {{"op": "paint_grid", "path": "<主体网格>", "layer": 2}},
      {{"op": "paint_grid", "path": "<前景网格>", "layer": 3}},
    ])

  背景层：大色块为主，细节少，颜色偏冷偏暗，不抢主体
  主体层：视觉焦点，细节最多，颜色最丰富
  前景层：前景细节（草地、雾气、光效），只画必要的东西

  描边直接写进主体层的网格规划（轮廓色占一个字符），
  没有单独的描边 op。

第3步：调整图层混合
  透明度（0-255，128=半透明）和混合模式（normal / multiply / screen /
  overlay / darken / lighten，完整列表见 aseprite://blendmodes）
  **同样没有对应的 op**，要调得走 run_lua（unsafe + confirmed）。
  建议尝试：
    - 阴影层用 multiply 让阴影更自然
    - 光效层用 screen 或 lighten 增加光感

  不折腾混合模式也能出好效果 —— 调色和层次本来就在网格规划里。

第4步：inspect 整体预览与迭代
  inspect(session_id, scale=4) 合成预览（默认 view="composite"），
  看整体效果和量化指标：
  - 各层是否协调，主体是否突出？
  - color_count 是否还在节制范围内？
  - bbox 是否落在预期区域、coverage 是否合理？
  至少迭代2轮，只改有问题的那一层（指定 layer 参数）。

第5步：保存
  apply_operations(ops=[{{"op": "save_sprite"}}])

══════════════════════════════════════════
诚实的能力边界：
══════════════════════════════════════════
  - 建层/图层属性 → add_layer / set_layer / delete_layer；混合模式才用 run_lua
  - 帧的相关操作 → 用 add_frames / set_durations / add_tag，不必碰 Lua
  - 其余绘制 → apply_operations 的 op 就够了
  - 收工销毁会话 → close_session 是破坏性 op，需要 confirmed=true
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
        tile_w, tile_h = _parse_size(tile_size)
        canvas_w = tile_w * cols
        canvas_h = tile_h * rows

        return f"""请使用 Aseprite MCP 创建瓦片集：{description}

参数：{tile_size} 瓦片，{cols}x{rows} 布局（画布 {canvas_w}x{canvas_h}）

{_TOOL_SURFACE}

══════════════════════════════════════════
专业 Tileset 工作流程（docs §8）：
══════════════════════════════════════════

第1步：建瓦片画布
  没有"建瓦片画布"的专用 op —— 画布就是一张普通大画布，
  尺寸自己算出来（tile_size={tile_w}，所以 {cols}x{rows} 格 = {canvas_w}x{canvas_h}）：

    apply_operations(ops=[
      {{"op": "create_sprite", "width": {canvas_w}, "height": {canvas_h}}},
    ])

  注意：坐标网格和"瓦片网格"是两回事。Aseprite 里那个网格线只是编辑器辅助，
  不会替你划格子；边界要自己在规划时对齐到 tile_size 的整数倍位置。

第2步：读取瓦片模板（可选参考）
  读取 aseprite://tileset/templates 查看可用模板，
  读取 aseprite://tileset/templates/{{name}} 取具体 grid/colormap。
  它们给的是 grid 行串 + "字符=#RRGGBB" 映射，改写成上面那种 Lua
  {{palette=..., rows=...}} 文件就能直接喂给 paint_grid。

第3步：逐块绘制
  每块瓦片一个网格文件，用 paint_grid 的 x/y 摆到对应格子：
  第 r 行第 c 列瓦片的左上角 = (c × {tile_w}, r × {tile_h})。

    apply_operations(ops=[
      {{"op": "paint_grid", "path": "<中心块网格>", "x": {tile_w}, "y": {tile_h}}},
      {{"op": "paint_grid", "path": "<边缘块网格>", "x": 0, "y": {tile_h}}},
    ])

  完整一套需：中心块、边缘块、角块、过渡瓦片、装饰块（docs §8.3）。
  一批里可以放多个块的 paint_grid，一次提交。

第4步：检查接缝（必须执行！）
  没有"拼接预览"工具，用 inspect 顶替 —— 它的只读预览可以放大观察：
  inspect(session_id, scale=4) 看清每一块的边缘像素，再逐块比对：
  - 边缘像素是否与相邻瓦片匹配？
  - 是否有 1 像素偏移？
  有接缝 → 修正该瓦片边缘像素 → 再次 inspect 验证。
  一块接缝就是一处返工，逐块过一遍比整体返工便宜。

第5步：保存
  apply_operations(ops=[{{"op": "save_sprite"}}])

══════════════════════════════════════════
理想调用次数（docs §8 工作流）：
══════════════════════════════════════════
  create_sprite(1) → paint_grid(N块，可分批提交) → inspect(1~2)
  → [修正] → paint_grid(仅修正边缘) → save_sprite(1)
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
说明：K=轮廓, R=底色, W=高光, S=阴影, .=不画
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
说明：K=轮廓, R=底色, W=高光, S=阴影, .=不画
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
  心形：K=#000000, R=#E74C3C, S=#C0392B, W=#FFB3B3, .=不画
  星星：K=#000000, Y=#FFEC27, O=#FFA300, W=#FFF8DC, .=不画
  剑：  K=#000000, B=#C0C0C0, D=#808080, G=#8B4513, W=#FFFFFF, .=不画
  盾：  K=#000000, B=#2980B9, D=#1B4F72, G=#DAA520, W=#FFFFFF, .=不画
  药水：K=#000000, R=#E74C3C, S=#C0392B, W=#FFB3B3, G=#2ECC71, .=不画""",
}