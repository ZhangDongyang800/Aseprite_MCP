"""Shared pytest fixtures."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import sys
import os

# Make sure the src package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_work_dir(tmp_path, monkeypatch):
    """Use a temp directory as the work dir so the real filesystem stays clean."""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.setenv("ASEPRITE_WORK_DIR", str(work_dir))
    return work_dir


@pytest.fixture
def mock_runner():
    """A mocked AsepriteRunner; real Aseprite never runs."""
    runner = MagicMock()
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}
    return runner


@pytest.fixture
def session_manager(tmp_work_dir):
    """A SessionManager backed by the temporary work directory."""
    from src.session import SessionManager
    from src.config import Config

    config = Config()
    # Make sure the temporary work directory is used
    config.work_dir = tmp_work_dir
    return SessionManager(config)
