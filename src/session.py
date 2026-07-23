"""会话管理模块。

每个会话对应一个独立的工作目录，包含一个 .ase 画布文件。
会话通过 session_id（UUID）标识，支持创建、查询、销毁和超时清理。
"""

import uuid
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from src.config import Config


@dataclass
class SessionManager:
    """管理绘制会话的生命周期。

    每个会话维护：
    - session_id: UUID 字符串
    - 工作目录: <work_dir>/<session_id>/
    - .ase 文件: <工作目录>/canvas.ase
    - 画布信息: width, height, color_mode
    - 时间戳: created_at, last_activity
    """

    config: Config

    # 内部会话存储：session_id → 会话数据字典
    _sessions: dict = field(default_factory=dict, init=False, repr=False)

    def create_session(
        self, width: int, height: int, color_mode: str = "rgb"
    ) -> str:
        """创建新会话。

        Args:
            width: 画布宽度（像素）
            height: 画布高度（像素）
            color_mode: 颜色模式（"rgb", "grayscale", "indexed"）

        Returns:
            session_id: 新会话的 UUID 字符串
        """
        session_id = str(uuid.uuid4())
        now = time.time()

        # 创建工作目录
        work_dir = self.config.work_dir / session_id
        work_dir.mkdir(parents=True, exist_ok=True)

        # 记录会话数据
        self._sessions[session_id] = {
            "session_id": session_id,
            "work_dir": work_dir,
            "ase_path": work_dir / "canvas.ase",
            "width": width,
            "height": height,
            "color_mode": color_mode,
            "created_at": now,
            "last_activity": now,
        }

        return session_id

    def _get_session(self, session_id: str) -> dict:
        """获取会话数据，更新最后活动时间。

        Args:
            session_id: 会话 ID

        Returns:
            会话数据字典

        Raises:
            KeyError: 会话不存在时抛出
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")

        # 更新最后活动时间
        self._sessions[session_id]["last_activity"] = time.time()
        return self._sessions[session_id]

    def get_work_dir(self, session_id: str) -> Path:
        """获取会话的工作目录路径。"""
        return self._get_session(session_id)["work_dir"]

    def get_ase_path(self, session_id: str) -> Path:
        """获取会话的 .ase 画布文件路径。"""
        return self._get_session(session_id)["ase_path"]

    def get_canvas_info(self, session_id: str) -> dict:
        """获取画布元数据。"""
        session = self._get_session(session_id)
        return {
            "width": session["width"],
            "height": session["height"],
            "color_mode": session["color_mode"],
        }

    def update_canvas_info(
        self, session_id: str, width: int, height: int
    ) -> None:
        """更新会话的画布尺寸缓存。

        用于 import_png 等场景：从外部文件导入后，实际尺寸可能与
        创建会话时的占位尺寸不同，需要用真实尺寸刷新缓存，
        保证后续 get_canvas_info 返回正确值。

        Args:
            session_id: 会话 ID
            width: 真实画布宽度（像素）
            height: 真实画布高度（像素）
        """
        session = self._get_session(session_id)
        session["width"] = width
        session["height"] = height

    def close_session(self, session_id: str) -> None:
        """关闭会话，删除工作目录。

        Args:
            session_id: 会话 ID

        Raises:
            KeyError: 会话不存在时抛出
        """
        session = self._get_session(session_id)
        work_dir = session["work_dir"]

        # 删除工作目录
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

        # 从内存中移除
        del self._sessions[session_id]

    def list_sessions(self) -> list[dict]:
        """列出所有活跃会话。

        Returns:
            会话信息列表，每项包含 session_id, width, height, color_mode
        """
        result = []
        for session_id, data in self._sessions.items():
            result.append({
                "session_id": session_id,
                "width": data["width"],
                "height": data["height"],
                "color_mode": data["color_mode"],
            })
        return result

    def cleanup_expired(self) -> None:
        """清理超时会话。

        删除最后活动时间超过 session_timeout 的会话。
        """
        now = time.time()
        expired_ids = []

        for session_id, data in self._sessions.items():
            if now - data["last_activity"] > self.config.session_timeout:
                expired_ids.append(session_id)

        for session_id in expired_ids:
            self.close_session(session_id)
