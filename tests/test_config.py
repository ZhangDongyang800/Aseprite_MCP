"""配置管理模块的测试。"""

import os
from pathlib import Path
from unittest.mock import patch


def test_default_aseprite_path():
    """测试默认 Aseprite 路径。"""
    from src.config import Config

    # 清除环境变量以测试默认值
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ASEPRITE_PATH", None)
        config = Config()
        expected = r"D:\cxdownload\game_develop\Aseprite-v1.3.17.2-Source\build\bin\aseprite.exe"
        assert config.aseprite_path == expected


def test_custom_aseprite_path_via_env():
    """测试通过环境变量自定义 Aseprite 路径。"""
    from src.config import Config

    with patch.dict(os.environ, {"ASEPRITE_PATH": "/custom/path/aseprite.exe"}):
        config = Config()
        assert config.aseprite_path == "/custom/path/aseprite.exe"


def test_default_work_dir():
    """测试默认工作目录。"""
    from src.config import Config

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ASEPRITE_WORK_DIR", None)
        config = Config()
        assert config.work_dir == Path("./work")


def test_custom_work_dir_via_env():
    """测试通过环境变量自定义工作目录。"""
    from src.config import Config

    with patch.dict(os.environ, {"ASEPRITE_WORK_DIR": "/tmp/custom_work"}):
        config = Config()
        assert config.work_dir == Path("/tmp/custom_work")


def test_default_session_timeout():
    """测试默认会话超时时间。"""
    from src.config import Config

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ASEPRITE_SESSION_TIMEOUT", None)
        config = Config()
        assert config.session_timeout == 3600


def test_custom_session_timeout_via_env():
    """测试通过环境变量自定义超时时间。"""
    from src.config import Config

    with patch.dict(os.environ, {"ASEPRITE_SESSION_TIMEOUT": "7200"}):
        config = Config()
        assert config.session_timeout == 7200


def test_scripts_dir_is_always_relative_to_package():
    """测试脚本目录总是相对于 src 包定位。"""
    from src.config import Config

    config = Config()
    # scripts 目录应与 src 同级
    expected_parent = Path(__file__).parent.parent
    assert config.scripts_dir == expected_parent / "scripts"
