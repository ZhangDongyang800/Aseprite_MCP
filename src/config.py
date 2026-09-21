"""配置管理模块。

从环境变量读取配置，提供合理默认值。
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _warn_unusable_work_dir(path: Path) -> None:
    """Complain at startup instead of failing every later call obscurely.

    Aseprite cannot load a script whose path contains non-ASCII characters and reports it as a
    missing Lua engine, which reads as a build problem rather than a configuration one.
    """
    if not str(path).isascii():
        print(
            f"WARNING: ASEPRITE_WORK_DIR is not ASCII-only: {path}\n"
            f"Aseprite will reject script paths containing non-ASCII characters and report it "
            f"as a missing Lua engine. Point ASEPRITE_WORK_DIR at an ASCII path.",
            file=sys.stderr,
        )


@dataclass
class Config:
    """MCP 服务器配置。

    通过环境变量可覆盖默认值：
    - ASEPRITE_PATH: Aseprite 可执行文件路径
    - ASEPRITE_WORK_DIR: 会话工作目录根（默认 <repo>/work）
    - ASEPRITE_SESSION_TIMEOUT: 会话超时时间（秒）
    - ASEPRITE_MCP_MODE: 执行模式（"cli" 或 "ws"），默认 "cli"
    - ASEPRITE_WS_HOST: WebSocket server 监听地址，默认 "127.0.0.1"
    - ASEPRITE_WS_PORT: WebSocket server 监听端口，默认 9001
    """

    # Aseprite 可执行文件路径（默认指向用户本机编译版本）
    aseprite_path: str = None

    # 会话工作目录
    work_dir: Path = None

    # 会话超时时间（秒）
    session_timeout: int = None

    # Lua 脚本目录（自动定位，不可通过环境变量配置）
    scripts_dir: Path = None

    # 执行模式："cli"（传统 CLI subprocess）或 "ws"（WebSocket 实时模式）
    mode: str = None

    # WebSocket server 配置（仅 mode="ws" 时生效）
    ws_host: str = None
    ws_port: int = None

    def __post_init__(self):
        """从环境变量加载配置，应用默认值。"""
        # Aseprite 可执行文件路径
        if self.aseprite_path is None:
            from src.aseprite_locate import locate_aseprite

            self.aseprite_path = (
                os.environ.get("ASEPRITE_PATH")
                or locate_aseprite()
                or "aseprite"
            )

        # 会话工作目录：默认落在仓库根下。相对路径会解析到宿主给进程的任意 cwd，
        # 那个目录既可能不可写，也可能把会话文件撒到意想不到的地方。
        if self.work_dir is None:
            self.work_dir = Path(
                os.environ.get("ASEPRITE_WORK_DIR") or _REPO_ROOT / "work"
            )
        self.work_dir = Path(self.work_dir).expanduser().resolve()
        _warn_unusable_work_dir(self.work_dir)

        # 会话超时时间
        if self.session_timeout is None:
            self.session_timeout = int(
                os.environ.get("ASEPRITE_SESSION_TIMEOUT", "3600")
            )

        # Lua 脚本目录：自动定位为 src 包的父目录下的 scripts/
        # 即 <项目根>/scripts/
        self.scripts_dir = Path(__file__).parent.parent / "scripts"

        # 执行模式：cli（默认）或 ws（WebSocket 实时模式）
        if self.mode is None:
            self.mode = os.environ.get("ASEPRITE_MCP_MODE", "cli")

        # WebSocket server 配置
        if self.ws_host is None:
            self.ws_host = os.environ.get("ASEPRITE_WS_HOST", "127.0.0.1")
        if self.ws_port is None:
            self.ws_port = int(os.environ.get("ASEPRITE_WS_PORT", "9001"))

    # Properties rather than fields: tests and callers reassign work_dir after construction.
    @property
    def sessions_dir(self) -> Path:
        """Where the server keeps session state. Nothing else belongs here."""
        return self.work_dir / "sessions"

    @property
    def appdata_dir(self) -> Path:
        """Stand-in %APPDATA% for hosts that strip it; infrastructure, not session data."""
        return self.work_dir / ".appdata"
