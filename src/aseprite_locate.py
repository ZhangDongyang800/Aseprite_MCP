"""跨平台定位 Aseprite 可执行文件。"""

import os
import shutil
import sys
from pathlib import Path


def _candidate_paths() -> list[Path]:
    home = Path.home()
    if sys.platform == "win32":
        return [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Aseprite" / "aseprite.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Aseprite" / "aseprite.exe",
            Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "Aseprite" / "aseprite.exe",
            Path("C:/Program Files (x86)/Steam/steamapps/common/Aseprite/aseprite.exe"),
            Path("D:/Steam/steamapps/common/Aseprite/aseprite.exe"),
            Path("D:/SteamLibrary/steamapps/common/Aseprite/aseprite.exe"),
        ]
    if sys.platform == "darwin":
        return [
            Path("/Applications/Aseprite.app/Contents/MacOS/aseprite"),
            home / "Applications" / "Aseprite.app" / "Contents" / "MacOS" / "aseprite",
        ]
    return [
        Path("/usr/bin/aseprite"),
        Path("/usr/local/bin/aseprite"),
        home / ".local" / "bin" / "aseprite",
        Path("/snap/bin/aseprite"),
    ]


def locate_aseprite() -> str | None:
    """返回可执行文件路径；优先 ASEPRITE_PATH，然后 PATH，最后常见安装位置。"""
    env = os.environ.get("ASEPRITE_PATH")
    if env and Path(env).exists():
        return env
    found = shutil.which("aseprite") or shutil.which("aseprite.exe")
    if found:
        return found
    for candidate in _candidate_paths():
        if candidate.exists():
            return str(candidate)
    return None
