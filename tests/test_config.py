"""配置管理模块的测试。"""

import os
from pathlib import Path
from unittest.mock import patch


def test_aseprite_path_uses_detected_path(monkeypatch, tmp_path):
    """测试未设置环境变量时使用自动探测结果。"""
    from src import aseprite_locate
    from src.config import Config

    fake = str(tmp_path / "aseprite.exe")
    monkeypatch.delenv("ASEPRITE_PATH", raising=False)
    monkeypatch.setattr(aseprite_locate, "locate_aseprite", lambda: fake)
    assert Config().aseprite_path == fake


def test_aseprite_path_falls_back_to_command_name(monkeypatch):
    """测试探测失败时回退到 "aseprite" 交由系统解析。"""
    from src import aseprite_locate
    from src.config import Config

    monkeypatch.delenv("ASEPRITE_PATH", raising=False)
    monkeypatch.setattr(aseprite_locate, "locate_aseprite", lambda: None)
    assert Config().aseprite_path == "aseprite"


def test_env_path_takes_precedence_over_detection(monkeypatch, tmp_path):
    """测试 ASEPRITE_PATH 优先于自动探测。"""
    from src import aseprite_locate
    from src.config import Config

    env_path = str(tmp_path / "env-aseprite.exe")
    monkeypatch.setenv("ASEPRITE_PATH", env_path)
    monkeypatch.setattr(aseprite_locate, "locate_aseprite", lambda: "detected")
    assert Config().aseprite_path == env_path


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


def test_locate_prefers_env(monkeypatch, tmp_path):
    from src.aseprite_locate import locate_aseprite

    fake = tmp_path / "aseprite.exe"
    fake.write_text("x")
    monkeypatch.setenv("ASEPRITE_PATH", str(fake))
    assert locate_aseprite() == str(fake)


def test_locate_returns_none_when_missing(monkeypatch, tmp_path):
    from src.aseprite_locate import locate_aseprite

    monkeypatch.setenv("ASEPRITE_PATH", str(tmp_path / "nope.exe"))
    monkeypatch.setattr(
        "src.aseprite_locate._candidate_paths", lambda: [tmp_path / "nope2.exe"]
    )
    assert locate_aseprite() is None
