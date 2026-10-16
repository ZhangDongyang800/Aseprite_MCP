"""端到端测试：对真实 Aseprite 跑完整的 v2 三工具面。

与被删除的 tests/test_e2e.py 不同，这里的可用性判定走服务器自己那条解析链
（ASEPRITE_PATH → src.aseprite_locate.locate_aseprite()），不再硬编码某个开发者的路径；
fixture 也按 server.py 的接线搭（Config + SessionManager + AsepriteRunner +
register_v2_tools），断言全部落在真实产物上：.ase 文件、inspect 的 metrics/meta。

前置条件：安装 Aseprite，或用 ASEPRITE_PATH 指向可执行文件。
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.aseprite_locate import locate_aseprite
from src.config import Config
from src.runner import AsepriteRunner
from src.session import SessionManager
from src.v2.tools import register_v2_tools

pytestmark = pytest.mark.e2e


def _resolve_aseprite() -> Path | None:
    """和 Config.__post_init__ 一样：环境变量优先，否则自动探测，最后必须真的存在。"""
    env = os.environ.get("ASEPRITE_PATH")
    if env:
        return Path(env) if Path(env).exists() else None
    found = locate_aseprite()
    return Path(found) if found and Path(found).exists() else None


ASEPRITE = _resolve_aseprite()

skip_reason = (
    "Aseprite not found. Set ASEPRITE_PATH to the aseprite executable "
    "(Config also probes PATH and the usual install locations)."
)
skip_no_aseprite = pytest.mark.skipif(ASEPRITE is None, reason=skip_reason)


@pytest.fixture
def api(tmp_path, monkeypatch):
    """真实 runner + 真实 session 工作目录，接线与 server.py create_server() 一致。"""
    if ASEPRITE is None:
        pytest.skip(skip_reason)
    monkeypatch.setenv("ASEPRITE_PATH", str(ASEPRITE))

    config = Config()
    config.work_dir = tmp_path / "work"
    config.work_dir.mkdir()
    config.mode = "cli"

    session_manager = SessionManager(config)
    runner = AsepriteRunner(config)
    if not runner.check_aseprite_exists():
        pytest.skip(f"Aseprite not usable at {config.aseprite_path}")

    captured = {}

    def capture(func=None, **kwargs):
        if func is None:
            return lambda f: capture(f, **kwargs)
        captured[func.__name__] = func
        return func

    mcp = MagicMock()
    mcp.tool = capture
    engine = register_v2_tools(mcp, session_manager, runner, config)

    return SimpleNamespace(
        apply=captured["apply_operations"],
        inspect=captured["inspect"],
        run_lua=captured["run_lua"],
        engine=engine,
        sm=session_manager,
        config=config,
    )


def _metrics(api, session_id):
    """inspect 的结构化结果，失败时把信封内容摊开成断言消息。"""
    result = api.inspect(session_id=session_id, scale=1)
    payload = result.structured_content
    assert payload["ok"], payload
    return payload["meta"], payload["metrics"]


@skip_no_aseprite
def test_create_and_draw_produce_the_expected_pixels(api):
    """create + draw_pixel + draw_rect：.ase 落盘，metrics 里的颜色/bbox/覆盖率都对得上。"""
    env = api.apply(ops=[
        {"op": "create_sprite", "width": 8, "height": 8},
        {"op": "draw_pixel", "x": 1, "y": 2, "color": "#FF0000"},
        {"op": "draw_rect", "x": 4, "y": 4, "width": 3, "height": 2,
         "color": "#00FF00", "filled": True},
    ])
    assert env.ok, env.error
    assert env.changed is True

    sid = env.session_id
    assert sid
    ase = api.sm.get_ase_path(sid)
    assert ase.exists() and ase.stat().st_size > 0, "create_sprite must leave a real .ase"

    meta, metrics = _metrics(api, sid)
    assert (meta["width"], meta["height"]) == (8, 8)
    assert metrics["width"] == 8 and metrics["height"] == 8
    assert set(metrics["palette"]) == {"#FF0000", "#00FF00"}
    # (1,2) 单点 + (4..6, 4..5) 实心矩形 = 7 个不透明像素
    assert metrics["bbox"] == {"x": 1, "y": 2, "width": 6, "height": 4}
    assert metrics["coverage"] == pytest.approx(7 / 64)
    assert metrics["color_count"] == 2

    work = api.sm.get_work_dir(sid)
    assert (work / "preview.png").exists(), "inspect must write the preview it advertises"
    assert (work / "metrics.json").exists()


@skip_no_aseprite
def test_undo_redo_roundtrip_restores_the_previous_canvas(api):
    """undo 退回上一个快照，redo 再把它换回来——两次都用 inspect 读真实像素验证。"""
    env = api.apply(ops=[
        {"op": "create_sprite", "width": 6, "height": 6},
        {"op": "draw_pixel", "x": 0, "y": 0, "color": "#FF0000"},
    ])
    assert env.ok, env.error
    sid = env.session_id

    env2 = api.apply(ops=[{"op": "draw_pixel", "x": 5, "y": 5, "color": "#0000FF"}],
                     session_id=sid)
    assert env2.ok, env2.error
    assert env2.undo.available is True
    assert set(_metrics(api, sid)[1]["palette"]) == {"#FF0000", "#0000FF"}

    undone = api.apply(ops=[{"op": "undo"}], session_id=sid)
    assert undone.ok, undone.error
    _, after_undo = _metrics(api, sid)
    assert after_undo["palette"] == ["#FF0000"], "undo must drop the blue pixel"
    assert after_undo["bbox"] == {"x": 0, "y": 0, "width": 1, "height": 1}

    redone = api.apply(ops=[{"op": "redo"}], session_id=sid)
    assert redone.ok, redone.error
    _, after_redo = _metrics(api, sid)
    assert set(after_redo["palette"]) == {"#FF0000", "#0000FF"}
    assert after_redo["bbox"] == {"x": 0, "y": 0, "width": 6, "height": 6}


@skip_no_aseprite
def test_structural_ops_survive_a_save_and_reopen(api, tmp_path):
    """add_frames/set_durations/add_tag 写进 .ase：另存一份再用新会话打开核对。"""
    env = api.apply(ops=[
        {"op": "create_sprite", "width": 4, "height": 4},
        {"op": "add_frames", "count": 3, "duration": 0.1},
        {"op": "set_durations", "durations": [0.1, 0.2, 0.3, 0.4]},
        {"op": "add_tag", "name": "walk", "from_frame": 1, "to_frame": 4},
    ])
    assert env.ok, env.error
    sid = env.session_id

    meta, _ = _metrics(api, sid)
    assert meta["frames_total"] == 4
    assert [round(f["duration"], 3) for f in meta["frames"]] == [0.1, 0.2, 0.3, 0.4]
    assert meta["tags"] == [{"name": "walk", "from": 1, "to": 4}]

    saved = tmp_path / "final.ase"
    assert api.apply(ops=[{"op": "save_sprite", "path": str(saved)}],
                     session_id=sid).ok
    assert saved.exists() and saved.stat().st_size > 0

    # 只有存进 .ase 的东西才会跟着新会话回来；只查内存里的 sprite 说明不了持久化。
    reopened = api.apply(ops=[{"op": "open_sprite", "path": str(saved)}])
    assert reopened.ok, reopened.error
    meta2, metrics2 = _metrics(api, reopened.session_id)
    assert meta2["frames_total"] == 4
    assert [round(f["duration"], 3) for f in meta2["frames"]] == [0.1, 0.2, 0.3, 0.4]
    assert meta2["tags"] == [{"name": "walk", "from": 1, "to": 4}]
    assert (meta2["width"], meta2["height"]) == (4, 4)
    assert metrics2["color_count"] == 0, "add_frames(count=3) must leave blank frames"


@skip_no_aseprite
def test_paint_grid_paints_a_lua_grid_from_the_session_work_dir(api):
    """paint_grid：工作目录内的 Lua 网格文件不需要 confirmed=true，直接画出精确像素。"""
    env = api.apply(ops=[
        {"op": "create_sprite", "width": 8, "height": 8},
    ])
    assert env.ok, env.error
    sid = env.session_id

    grid = api.sm.get_work_dir(sid) / "grid.lua"
    grid.write_text(
        'return {palette = {a = "#FF0000", b = "#0000FF"},\n'
        '        rows = {"a.", ".b", "ab"}}\n',
        encoding="utf-8",
    )

    painted = api.apply(ops=[{"op": "paint_grid", "path": str(grid)}], session_id=sid)
    assert painted.ok, painted.error
    results = {r.op: r.data for r in painted.op_results}
    assert results["paint_grid"]["painted"] == 4
    assert results["paint_grid"]["width"] == 2 and results["paint_grid"]["height"] == 3

    _, metrics = _metrics(api, sid)
    assert set(metrics["palette"]) == {"#FF0000", "#0000FF"}
    assert metrics["bbox"] == {"x": 0, "y": 0, "width": 2, "height": 3}
    assert metrics["coverage"] == pytest.approx(4 / 64)


@skip_no_aseprite
def test_out_of_bounds_draw_is_reported_not_silently_dropped(api):
    """Aseprite 的 image:drawPixel 越界不报错，op 必须替它把问题说出来。"""
    env = api.apply(ops=[
        {"op": "create_sprite", "width": 4, "height": 4},
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"},
    ])
    assert env.ok, env.error
    sid = env.session_id

    off_canvas = api.apply(ops=[{"op": "draw_pixel", "x": 999, "y": 999,
                                 "color": "#00FF00"}], session_id=sid)
    assert off_canvas.ok is False, "an out-of-bounds pixel must not report success"
    assert off_canvas.error is not None
    assert off_canvas.changed is False
    assert "999,999" in off_canvas.error.message
    assert "4x4" in off_canvas.error.message

    # 回滚是真回滚：越界那一批不能留下任何像素。
    _, metrics = _metrics(api, sid)
    assert metrics["palette"] == ["#FF0000"]

    too_big = api.apply(ops=[{"op": "draw_rect", "x": 2, "y": 2, "width": 8, "height": 2,
                              "color": "#00FF00", "filled": True}], session_id=sid)
    assert too_big.ok is False
    assert "2,2" in too_big.error.message
