"""Aseprite executors.

Two execution modes:
1. CLI mode (AsepriteRunner): calls the Aseprite CLI through a subprocess
   (aseprite -b --script); every call is its own process and state travels through the
   .ase file.
2. WebSocket mode (WebSocketRunner): sends commands over WebSocket to the extension inside
   a running Aseprite, so the AI drives the instance the user can see - state persists and
   the UI updates live.

Both modes expose the identical run_script() interface, so the tool layer never has to
know which one it is talking to.
"""

import os
import subprocess
from pathlib import Path
from dataclasses import dataclass

from src.config import Config


def _aseprite_env(appdata_dir: Path) -> dict:
    """Aseprite aborts at startup when APPDATA is unset, so hosts that strip it
    (stdio MCP children) fail with a misleading "Error creating directory"."""
    env = dict(os.environ)
    missing = [k for k in ("APPDATA", "LOCALAPPDATA") if not env.get(k)]
    if missing:
        cfg = appdata_dir / "Aseprite"
        cfg.mkdir(parents=True, exist_ok=True)
        for k in missing:
            env[k] = str(appdata_dir)
    return env


@dataclass
class AsepriteRunner:
    """Aseprite CLI executor.

    Wraps the subprocess call and builds aseprite -b --script-param k=v --script xxx.lua.
    Note: --script-param must precede --script, otherwise app.params is empty.
    """

    config: Config

    def run_script(
        self, script_name: str, params: dict
    ) -> dict:
        """Run an Aseprite Lua script.

        Args:
            script_name: Lua script file name (e.g. "draw_pixel.lua")
            params: parameters passed to the script (all values become strings)

        Returns:
            result dict:
            - success: {"success": True, "stdout": "...", "stderr": "..."}
            - failure: {"success": False, "stdout": "...", "stderr": "...", "error": "..."}
        """
        return self._invoke(self._build_cmd(self.config.scripts_dir / script_name, params))

    def check_aseprite_exists(self) -> bool:
        """Check whether the Aseprite executable exists.

        Returns:
            True when the path exists, False otherwise
        """
        return Path(self.config.aseprite_path).exists()

    def run_script_path(self, script_path: str, params: dict) -> dict:
        """Execute an Aseprite Lua script by absolute path (for run_lua escape hatch).

        Unlike run_script which looks up scripts_dir/<script_name>, this takes
        an absolute path to a Lua file directly.

        Args:
            script_path: Absolute path to the Lua script
            params: Dictionary of parameters

        Returns:
            Result dict (same format as run_script)
        """
        return self._invoke(self._build_cmd(script_path, params))

    def _build_cmd(self, script_path, params: dict) -> list:
        """aseprite -b --script-param k=v ... --script <path>

        --script-param must precede --script: Aseprite ignores parameters that come after it,
        and app.params silently ends up empty.
        """
        cmd = [self.config.aseprite_path, "-b"]
        for key, value in params.items():
            cmd.extend(["--script-param", f"{key}={value}"])
        cmd.extend(["--script", str(script_path)])
        return cmd

    def _invoke(self, cmd: list) -> dict:
        """Run one batched Aseprite invocation; every failure mode maps to a result dict."""
        timeout = getattr(self.config, "script_timeout", 30) or 30
        try:
            # Force UTF-8 so a Windows GBK console cannot mangle the output and break the
            # JSON parsing
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_aseprite_env(self.config.appdata_dir),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"Aseprite script timeout: exceeded {timeout} seconds",
            }
        except FileNotFoundError as e:
            # Wording is a contract: classify_script_failure() maps it to aseprite_not_found.
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"Aseprite executable not found: {e}",
            }

        if result.returncode == 0:
            return {"success": True, "stdout": result.stdout, "stderr": result.stderr}
        return {
            "success": False,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": f"Aseprite exited with code {result.returncode}",
        }


@dataclass
class WebSocketRunner:
    """WebSocket-mode executor.

    Sends script-execution requests to the extension inside a running Aseprite through
    WebSocketBridge. Interface-compatible with AsepriteRunner, so the two are drop-in
    replacements for each other.

    Upside:
    - the AI drives the Aseprite instance the user can see
    - state persists (no reopening the .ase file on every call)
    - the UI shows the AI drawing in real time

    Limits:
    - the user has to install the extension and click "Toggle Connection"
    - WebSocket callbacks can lag when Aseprite is unfocused
    """

    bridge: object  # a WebSocketBridge instance
    config: Config

    def run_script(self, script_name: str, params: dict) -> dict:
        """Send a script-execution request to Aseprite over WebSocket.

        Args:
            script_name: Lua script file name (e.g. "draw_pixel.lua")
            params: script parameter dict (values become strings on the Aseprite side)

        Returns:
            result dict (same shape as AsepriteRunner.run_script):
            - success: {"success": True, "stdout": "...", "stderr": "..."}
            - failure: {"success": False, "stdout": "...", "stderr": "...", "error": "..."}
        """
        # Build the full script path (the Aseprite extension needs an absolute path to
        # dofile)
        # bridge.send_request already returns the AsepriteRunner shape, so pass it through
        script_path = str(self.config.scripts_dir / script_name)
        return self.bridge.send_request(script_path, params)

    def run_script_path(self, script_path: str, params: dict) -> dict:
        """Execute a Lua script by absolute path via WebSocket (for run_lua)."""
        return self.bridge.send_request(script_path, params)

    def check_aseprite_exists(self) -> bool:
        """Check whether the Aseprite extension is connected.

        Returns:
            True when an Aseprite client is connected, False otherwise
        """
        return self.bridge.is_connected()
