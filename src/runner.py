"""Aseprite 执行器模块。

提供两种执行模式：
1. CLI 模式（AsepriteRunner）：通过 subprocess 调用 Aseprite CLI（aseprite -b --script），
   每次调用是独立进程，通过 .ase 文件传递状态。
2. WebSocket 模式（WebSocketRunner）：通过 WebSocket 向运行中的 Aseprite 扩展发送命令，
   AI 直接操作用户可见的 Aseprite 实例，状态持久、UI 实时可见。

两种模式的 run_script() 接口完全一致，工具层无需感知底层差异。
"""

import subprocess
from pathlib import Path
from dataclasses import dataclass

from src.config import Config


@dataclass
class AsepriteRunner:
    """Aseprite CLI 执行器。

    封装 subprocess 调用，构造 aseprite -b --script-param k=v --script xxx.lua 命令。
    注意：--script-param 必须在 --script 之前，否则 app.params 为空。
    """

    config: Config

    def run_script(
        self, script_name: str, params: dict
    ) -> dict:
        """执行 Aseprite Lua 脚本。

        Args:
            script_name: Lua 脚本文件名（如 "draw_pixel.lua"）
            params: 传递给脚本的参数字典（所有值转为字符串）

        Returns:
            执行结果字典：
            - 成功: {"success": True, "stdout": "...", "stderr": "..."}
            - 失败: {"success": False, "stdout": "...", "stderr": "...", "error": "..."}
        """
        # 构造脚本完整路径
        script_path = self.config.scripts_dir / script_name

        # 构造命令行参数（--script-param 必须在 --script 之前）
        cmd = [
            self.config.aseprite_path,
            "-b",
        ]

        # 添加 --script-param 参数（必须在 --script 之前）
        for key, value in params.items():
            cmd.extend(["--script-param", f"{key}={value}"])

        # 添加 --script 参数（放在最后）
        cmd.extend(["--script", str(script_path)])

        try:
            # 执行命令（指定 UTF-8 编码，避免 Windows GBK 乱码导致 JSON 解析失败）
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,  # 30 秒超时
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            else:
                return {
                    "success": False,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": f"Aseprite exited with code {result.returncode}",
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"Aseprite script timeout: exceeded 30 seconds",
            }
        except FileNotFoundError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"Aseprite executable not found: {e}",
            }

    def check_aseprite_exists(self) -> bool:
        """检查 Aseprite 可执行文件是否存在。

        Returns:
            True 如果路径存在，False 否则
        """
        return Path(self.config.aseprite_path).exists()


@dataclass
class WebSocketRunner:
    """WebSocket 模式执行器。

    通过 WebSocketBridge 向运行中的 Aseprite 扩展发送脚本执行请求。
    与 AsepriteRunner 接口完全一致，可无缝替换。

    优势：
    - AI 直接操作用户可见的 Aseprite 实例
    - 状态持久（无需每次重新打开 .ase 文件）
    - UI 实时可见（用户能看到 AI 在画）

    限制：
    - 需要用户手动安装扩展并点击"Toggle Connection"
    - Aseprite 失焦时 WebSocket 回调可能延迟
    """

    bridge: object  # WebSocketBridge 实例
    config: Config

    def run_script(self, script_name: str, params: dict) -> dict:
        """通过 WebSocket 向 Aseprite 发送脚本执行请求。

        Args:
            script_name: Lua 脚本文件名（如 "draw_pixel.lua"）
            params: 脚本参数字典（所有值会在 Aseprite 端转为字符串）

        Returns:
            执行结果字典（与 AsepriteRunner.run_script 格式一致）：
            - 成功: {"success": True, "stdout": "...", "stderr": "..."}
            - 失败: {"success": False, "stdout": "...", "stderr": "...", "error": "..."}
        """
        # 构造完整脚本路径（Aseprite 扩展需要绝对路径来 dofile）
        # bridge.send_request 已返回与 AsepriteRunner 一致的格式，直接透传
        script_path = str(self.config.scripts_dir / script_name)
        return self.bridge.send_request(script_path, params)

    def check_aseprite_exists(self) -> bool:
        """检查 Aseprite 扩展是否已连接。

        Returns:
            True 如果有 Aseprite client 连接，False 否则
        """
        return self.bridge.is_connected()
