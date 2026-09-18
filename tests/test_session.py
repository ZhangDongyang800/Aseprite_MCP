"""SessionManager 测试。"""

import time
from pathlib import Path
import pytest


def test_create_session_returns_uuid_and_creates_dir(session_manager):
    """测试创建会话返回 session_id 并创建工作目录。"""
    session_id = session_manager.create_session(width=16, height=16, color_mode="rgb")

    # session_id 应是非空字符串
    assert isinstance(session_id, str)
    assert len(session_id) > 0

    # 工作目录应存在
    work_dir = session_manager.get_work_dir(session_id)
    assert work_dir.exists()
    assert work_dir.is_dir()


def test_create_session_ase_file_path(session_manager):
    """测试会话的 .ase 文件路径正确。"""
    session_id = session_manager.create_session(width=32, height=32)

    ase_path = session_manager.get_ase_path(session_id)
    assert ase_path.name == "canvas.ase"
    assert ase_path.parent == session_manager.get_work_dir(session_id)


def test_get_work_dir_raises_for_unknown_session(session_manager):
    """测试查询不存在的会话抛出 KeyError。"""
    with pytest.raises(KeyError, match="Session not found"):
        session_manager.get_work_dir("nonexistent-id")


def test_get_ase_path_raises_for_unknown_session(session_manager):
    """测试查询不存在的会话 .ase 路径抛出 KeyError。"""
    with pytest.raises(KeyError, match="Session not found"):
        session_manager.get_ase_path("nonexistent-id")


def test_close_session_removes_work_dir(session_manager):
    """测试关闭会话删除工作目录。"""
    session_id = session_manager.create_session(width=16, height=16)
    work_dir = session_manager.get_work_dir(session_id)
    assert work_dir.exists()

    session_manager.close_session(session_id)

    assert not work_dir.exists()
    with pytest.raises(KeyError):
        session_manager.get_work_dir(session_id)


def test_close_unknown_session_raises(session_manager):
    """测试关闭不存在的会话抛出 KeyError。"""
    with pytest.raises(KeyError, match="Session not found"):
        session_manager.close_session("nonexistent-id")


def test_update_canvas_info_refreshes_size(session_manager):
    """测试 update_canvas_info 用真实尺寸刷新会话缓存。"""
    # 创建占位会话（16x16，模拟 import_png 前的占位）
    session_id = session_manager.create_session(width=16, height=16)

    # 导入 PNG 后用真实尺寸刷新
    session_manager.update_canvas_info(session_id, width=32, height=24)

    info = session_manager.get_canvas_info(session_id)
    assert info["width"] == 32
    assert info["height"] == 24
    # color_mode 应保持不变
    assert info["color_mode"] == "rgb"


def test_update_canvas_info_unknown_session_raises(session_manager):
    """测试更新不存在的会话抛出 KeyError。"""
    with pytest.raises(KeyError, match="Session not found"):
        session_manager.update_canvas_info("nonexistent-id", 32, 32)


def test_list_sessions_returns_all_active(session_manager):
    """测试列出所有活跃会话。"""
    id1 = session_manager.create_session(width=16, height=16)
    id2 = session_manager.create_session(width=32, height=32)

    sessions = session_manager.list_sessions()

    assert len(sessions) == 2
    session_ids = [s["session_id"] for s in sessions]
    assert id1 in session_ids
    assert id2 in session_ids


def test_list_sessions_includes_canvas_info(session_manager):
    """测试会话列表包含画布尺寸信息。"""
    session_id = session_manager.create_session(width=16, height=16, color_mode="rgb")

    sessions = session_manager.list_sessions()
    target = [s for s in sessions if s["session_id"] == session_id][0]

    assert target["width"] == 16
    assert target["height"] == 16
    assert target["color_mode"] == "rgb"


def test_session_records_last_activity(session_manager):
    """测试会话记录最后活动时间。"""
    session_id = session_manager.create_session(width=16, height=16)

    # 触发活动
    time.sleep(0.01)
    session_manager.get_work_dir(session_id)

    # 最后活动时间应晚于创建时间
    session_data = session_manager._sessions[session_id]
    assert session_data["last_activity"] > session_data["created_at"]


def test_cleanup_expired_sessions(session_manager):
    """测试清理过期会话。"""
    # 设置超时为 0.1 秒
    session_manager.config.session_timeout = 0.1

    session_id = session_manager.create_session(width=16, height=16)
    work_dir = session_manager.get_work_dir(session_id)

    # 等待超时
    time.sleep(0.2)

    session_manager.cleanup_expired()

    assert not work_dir.exists()
    with pytest.raises(KeyError):
        session_manager.get_work_dir(session_id)


def test_cleanup_does_not_remove_active_sessions(session_manager):
    """测试清理不影响活跃会话。"""
    session_manager.config.session_timeout = 3600

    session_id = session_manager.create_session(width=16, height=16)
    work_dir = session_manager.get_work_dir(session_id)

    session_manager.cleanup_expired()

    assert work_dir.exists()
