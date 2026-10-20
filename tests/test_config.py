"""Tests for the configuration module."""

import os
from pathlib import Path
from unittest.mock import patch


def test_aseprite_path_uses_detected_path(monkeypatch, tmp_path):
    """With no env var set, the auto-detected path is used."""
    from src import aseprite_locate
    from src.config import Config

    fake = str(tmp_path / "aseprite.exe")
    monkeypatch.delenv("ASEPRITE_PATH", raising=False)
    monkeypatch.setattr(aseprite_locate, "locate_aseprite", lambda: fake)
    assert Config().aseprite_path == fake


def test_aseprite_path_falls_back_to_command_name(monkeypatch):
    """When detection fails, fall back to "aseprite" and let the system resolve it."""
    from src import aseprite_locate
    from src.config import Config

    monkeypatch.delenv("ASEPRITE_PATH", raising=False)
    monkeypatch.setattr(aseprite_locate, "locate_aseprite", lambda: None)
    assert Config().aseprite_path == "aseprite"


def test_env_path_takes_precedence_over_detection(monkeypatch, tmp_path):
    """ASEPRITE_PATH wins over auto-detection."""
    from src import aseprite_locate
    from src.config import Config

    env_path = str(tmp_path / "env-aseprite.exe")
    monkeypatch.setenv("ASEPRITE_PATH", env_path)
    monkeypatch.setattr(aseprite_locate, "locate_aseprite", lambda: "detected")
    assert Config().aseprite_path == env_path


def test_custom_aseprite_path_via_env():
    """The Aseprite path can be customized through the env var."""
    from src.config import Config

    with patch.dict(os.environ, {"ASEPRITE_PATH": "/custom/path/aseprite.exe"}):
        config = Config()
        assert config.aseprite_path == "/custom/path/aseprite.exe"


def test_default_work_dir_is_absolute_under_the_repo():
    """The default must not depend on the cwd the MCP host happened to spawn us in."""
    from src.config import Config

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ASEPRITE_WORK_DIR", None)
        config = Config()
        assert config.work_dir.is_absolute()
        assert config.work_dir.name == "work"
        assert config.work_dir.parent == Path(__file__).resolve().parents[1]


def test_custom_work_dir_via_env():
    """The work dir can be customized through the env var (resolved to absolute)."""
    from src.config import Config

    with patch.dict(os.environ, {"ASEPRITE_WORK_DIR": "/tmp/custom_work"}):
        config = Config()
        assert config.work_dir.is_absolute()
        assert config.work_dir.name == "custom_work"


def test_work_dir_layout_separates_sessions_from_infrastructure():
    from src.config import Config

    with patch.dict(os.environ, {"ASEPRITE_WORK_DIR": str(Path("D:/x/ase_work"))}):
        config = Config()
        assert config.sessions_dir == config.work_dir / "sessions"
        assert config.appdata_dir == config.work_dir / ".appdata"


def test_default_session_timeout():
    """Default session timeout."""
    from src.config import Config

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ASEPRITE_SESSION_TIMEOUT", None)
        config = Config()
        assert config.session_timeout == 3600


def test_custom_session_timeout_via_env():
    """The timeout can be customized through the env var."""
    from src.config import Config

    with patch.dict(os.environ, {"ASEPRITE_SESSION_TIMEOUT": "7200"}):
        config = Config()
        assert config.session_timeout == 7200


def test_scripts_dir_is_always_relative_to_package():
    """The scripts dir is always located relative to the src package."""
    from src.config import Config

    config = Config()
    # the scripts dir should sit next to src
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
