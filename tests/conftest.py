"""pytest 公共 fixtures。"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import sys
import os

# 确保能导入 src 包
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_work_dir(tmp_path, monkeypatch):
    """使用临时目录作为工作目录，避免污染真实文件系统。"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.setenv("ASEPRITE_WORK_DIR", str(work_dir))
    return work_dir


@pytest.fixture
def mock_runner():
    """Mock 的 AsepriteRunner，不执行真实 Aseprite。"""
    runner = MagicMock()
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}
    return runner


@pytest.fixture
def session_manager(tmp_work_dir):
    """使用临时工作目录的 SessionManager 实例。"""
    from src.session import SessionManager
    from src.config import Config

    config = Config()
    # 确保使用临时工作目录
    config.work_dir = tmp_work_dir
    return SessionManager(config)
