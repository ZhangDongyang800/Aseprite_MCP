"""工具辅助函数。

提供参数验证等公共工具。
"""

import re
from typing import Optional


# 十六进制颜色正则：#RRGGBB
_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_color(color: str) -> str:
    """验证十六进制颜色格式。

    Args:
        color: 颜色字符串，如 "#FF0000"

    Returns:
        大写的颜色字符串，如 "#FF0000"

    Raises:
        ValueError: 格式不合法时抛出
    """
    if not color or not _COLOR_PATTERN.match(color):
        raise ValueError(
            f"Invalid color format: {color!r}. Expected #RRGGBB (e.g. #FF0000)"
        )
    return color.upper()


def validate_session_id(session_id: Optional[str]) -> str:
    """验证 session_id 非空。

    Args:
        session_id: 会话 ID

    Returns:
        验证通过的 session_id

    Raises:
        ValueError: session_id 为空时抛出
    """
    if not session_id:
        raise ValueError("session_id is required")
    return session_id
