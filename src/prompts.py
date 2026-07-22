"""MCP Prompts：预定义工作流模板。

提供精灵创作引导和迭代审查引导，指导 AI 使用工具完成绘制任务。
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
        return f"""请使用 Aseprite MCP 工具绘制一个精灵：{description}

工作流程：
1. 调用 create_sprite 创建 {size} 画布
2. 使用 draw_pixel/draw_line/draw_rect 等工具绘制
3. 调用 get_canvas_preview 查看当前画布
4. 分析图片，判断是否需要修正
5. 重复绘制和预览，直到满意
6. 调用 save_sprite 保存最终结果

像素艺术技巧：
- {size} 适合简单图标，32x32 适合角色
- 使用有限的调色板（5-8 种颜色）
- 注意轮廓清晰，颜色对比
- 像素之间不要留空隙
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

工作流程：
1. 调用 get_canvas_preview 查看当前画布状态
2. 分析图片，定位需要修改的区域
3. 使用 clear_region 清除需要修正的部分
4. 使用 draw_pixel/draw_line/draw_rect 等工具重新绘制
5. 再次调用 get_canvas_preview 验证修正效果
6. 如果满意，调用 save_sprite 保存
"""
