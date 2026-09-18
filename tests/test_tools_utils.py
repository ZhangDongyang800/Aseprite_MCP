"""工具辅助函数测试。"""

import pytest
from src.tools.utils import validate_color, validate_session_id


def test_validate_color_valid_hex():
    """测试有效的十六进制颜色。"""
    assert validate_color("#FF0000") == "#FF0000"
    assert validate_color("#00ff00") == "#00FF00"
    assert validate_color("#abcdef") == "#ABCDEF"


def test_validate_color_uppercase():
    """测试小写颜色转为大写。"""
    assert validate_color("#ff0000") == "#FF0000"


def test_validate_color_invalid_no_hash():
    """测试缺少 # 前缀。"""
    with pytest.raises(ValueError, match="Invalid color format"):
        validate_color("FF0000")


def test_validate_color_invalid_length():
    """测试长度错误。"""
    with pytest.raises(ValueError, match="Invalid color format"):
        validate_color("#FF00")
    with pytest.raises(ValueError, match="Invalid color format"):
        validate_color("#FF0000FF")


def test_validate_color_invalid_chars():
    """测试非法字符。"""
    with pytest.raises(ValueError, match="Invalid color format"):
        validate_color("#GGGGGG")


def test_validate_session_id_valid():
    """测试有效的 session_id（非空字符串）。"""
    validate_session_id("abc-123-def")  # 不抛异常即通过


def test_validate_session_id_empty():
    """测试空 session_id。"""
    with pytest.raises(ValueError, match="session_id is required"):
        validate_session_id("")


def test_validate_session_id_none():
    """测试 None session_id。"""
    with pytest.raises(ValueError, match="session_id is required"):
        validate_session_id(None)
