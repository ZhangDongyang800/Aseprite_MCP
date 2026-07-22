"""Aseprite 执行器模块。

通过 subprocess 调用 Aseprite CLI，执行 Lua 脚本。
每次调用都是独立的进程，通过 .ase 文件传递状态。
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
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
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
