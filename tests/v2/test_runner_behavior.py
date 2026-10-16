"""Runner behaviour: one subprocess path, one error vocabulary, a configurable time budget."""

import subprocess
from unittest.mock import patch

from src.config import Config
from src.runner import AsepriteRunner


def _runner(tmp_path, **kwargs):
    config = Config()
    config.work_dir = tmp_path
    config.aseprite_path = "aseprite-fake"
    for key, value in kwargs.items():
        setattr(config, key, value)
    return AsepriteRunner(config)


def test_timeout_defaults_to_thirty_seconds(monkeypatch):
    monkeypatch.delenv("ASEPRITE_TIMEOUT", raising=False)
    assert Config().script_timeout == 30


def test_timeout_is_configurable_via_env(monkeypatch):
    monkeypatch.setenv("ASEPRITE_TIMEOUT", "90")
    assert Config().script_timeout == 90


def test_subprocess_gets_the_configured_timeout(tmp_path):
    runner = _runner(tmp_path, script_timeout=45)
    with patch("subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        runner.run_script("mcp_x.lua", {})

    assert run.call_args.kwargs["timeout"] == 45


def test_timeout_error_names_the_limit_instead_of_a_bare_code(tmp_path):
    runner = _runner(tmp_path, script_timeout=45)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="aseprite", timeout=45)):
        result = runner.run_script("mcp_x.lua", {})

    assert result["success"] is False
    assert "45" in result["error"]
    assert "timeout" in result["error"].lower()


def test_both_entrypoints_report_a_missing_binary_identically(tmp_path):
    """The error wording is the contract classify_script_failure keys on."""
    runner = _runner(tmp_path)
    boom = FileNotFoundError("WinError 2")
    with patch("subprocess.run", side_effect=boom):
        by_name = runner.run_script("mcp_x.lua", {})
        by_path = runner.run_script_path("C:/tmp/x.lua", {})

    assert by_name["success"] is False
    assert by_path["success"] is False
    assert "aseprite" in by_name["error"].lower()
    assert by_name["error"].lower().startswith(by_path["error"][:20].lower()[:7])


def test_script_param_always_precedes_script(tmp_path):
    """Aseprite silently ignores params that come after --script."""
    runner = _runner(tmp_path)
    with patch("subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        runner.run_script("mcp_x.lua", {"a": "1", "b": "2"})

    cmd = run.call_args.args[0]
    first_script = cmd.index("--script")
    assert all(cmd.index("--script-param") < first_script for _ in [0])
    assert cmd[:first_script].count("--script-param") == 2