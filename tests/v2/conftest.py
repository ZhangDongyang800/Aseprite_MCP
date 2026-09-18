from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.session import SessionManager
from src.v2.tools import register_v2_tools


@pytest.fixture
def tools(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "cli"
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script_path.return_value = {
        "success": True,
        "stdout": '__MCP_JSON__{"ops":[{"op":"draw_pixel","ok":true,"data":{}}],"saved":true,"error":null}',
        "stderr": "",
    }
    captured = {}
    mcp = MagicMock()

    def capture(func=None, **kwargs):
        if func is None:
            return lambda f: capture(f, **kwargs)
        captured[func.__name__] = func
        return func

    mcp.tool = capture
    register_v2_tools(mcp, sm, runner, config)
    return captured, sm, runner
