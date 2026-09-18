import json
from pathlib import Path
from unittest.mock import MagicMock

from fastmcp.tools import ToolResult
from PIL import Image as PILImage

from src.v2.inspect import compute_metrics

META = {"width": 2, "height": 2, "frames": [], "layers": [], "palette": [], "tags": []}


def _png(tmp_path: Path) -> Path:
    img = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(4):
        img.putpixel((x, 0), (255, 0, 0, 255))
    img.putpixel((7, 7), (0, 255, 0, 128))
    p = tmp_path / "p.png"
    img.save(p)
    return p


def _write_preview(script, params):
    preview = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    preview.putpixel((7, 7), (255, 0, 0, 255))
    preview.save(params["output"])
    metrics_src = PILImage.new("RGBA", (2, 2), (0, 0, 0, 0))
    metrics_src.putpixel((0, 0), (255, 0, 0, 255))
    metrics_src.save(params["metrics_output"])
    return {"success": True, "stdout": json.dumps(META), "stderr": ""}


def test_compute_metrics(tmp_path):
    m = compute_metrics(
        _png(tmp_path), {"width": 8, "height": 8, "frames": [], "layers": []}
    )
    assert m["color_count"] == 2
    assert m["semi_transparent_pixels"] == 1
    assert m["coverage"] == 5 / 64
    assert m["bbox"] == {"x": 0, "y": 0, "width": 8, "height": 8}
    assert m["isolated_pixels"] == 1


def test_near_duplicate_detection(tmp_path):
    img = PILImage.new("RGBA", (4, 4), (0, 0, 0, 0))
    img.putpixel((0, 0), (100, 100, 100, 255))
    img.putpixel((1, 0), (102, 100, 100, 255))
    p = tmp_path / "q.png"
    img.save(p)
    m = compute_metrics(p, {"width": 4, "height": 4, "frames": [], "layers": []})
    assert m["near_duplicate_colors"]


def test_inspect_calls_script_with_session_path_and_writes_preview(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_preview

    result = captured["inspect"](session_id=sid)

    work = sm.get_work_dir(sid)
    runner.run_script.assert_called_once_with(
        "inspect.lua",
        {
            "file": str(sm.get_ase_path(sid)),
            "output": str(work / "preview.png"),
            "metrics_output": str(work / "metrics_src.png"),
            "scale": "4",
            "view": "composite",
        },
    )
    assert (work / "preview.png").exists()
    assert (work / "metrics_src.png").exists()
    assert isinstance(result, ToolResult)
    assert result.is_error is False
    assert result.content[0].type == "image"
    assert result.structured_content["ok"] is True
    assert result.structured_content["meta"] == META
    # 指标必须来自 scale=1 的 metrics_src.png，而不是放大后的 preview.png
    metrics = result.structured_content["metrics"]
    assert metrics["width"] == 2
    assert metrics["height"] == 2
    assert metrics["color_count"] == 1
    assert metrics["bbox"] == {"x": 0, "y": 0, "width": 1, "height": 1}
    assert metrics["coverage"] == 1 / 4
    saved = json.loads((work / "metrics.json").read_text(encoding="utf-8"))
    assert saved == {"meta": META, "metrics": metrics}


def test_inspect_uses_metrics_output_param(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_preview

    captured["inspect"](session_id=sid)

    _, params = runner.run_script.call_args[0]
    assert params["metrics_output"] == str(sm.get_work_dir(sid) / "metrics_src.png")


def test_inspect_passes_scale_and_view(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_preview

    captured["inspect"](session_id=sid, scale=8, view="silhouette")

    _, params = runner.run_script.call_args[0]
    assert params["scale"] == "8"
    assert params["view"] == "silhouette"


def test_inspect_holds_session_lock(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.side_effect = _write_preview
    engine = captured["_engine"]
    metrics_json = sm.get_work_dir(sid) / "metrics.json"
    calls = []

    class RecordingLock:
        def __enter__(self):
            calls.append(("enter", runner.run_script.called, metrics_json.exists()))
            return self

        def __exit__(self, *exc):
            calls.append(("exit", runner.run_script.called, metrics_json.exists()))
            return False

    engine.session_lock = MagicMock(return_value=RecordingLock())

    captured["inspect"](session_id=sid)

    engine.session_lock.assert_called_once_with(sid)
    # 进入锁时脚本尚未跑；退出锁前脚本与 metrics.json 均已完成
    assert calls == [("enter", False, False), ("exit", True, True)]


def test_inspect_unknown_session(tools):
    captured, _, _ = tools
    result = captured["inspect"](session_id="missing")

    assert result.is_error is True
    assert result.structured_content["ok"] is False
    assert result.structured_content["error"]["code"] == "session_not_found"
    assert "session not found" in result.structured_content["error"]["message"]
    assert any("session not found" in getattr(block, "text", "") for block in result.content)


def test_inspect_runner_failure(tools):
    captured, sm, runner = tools
    sid = sm.create_session(2, 2)
    runner.run_script.return_value = {"success": False, "error": "boom"}

    result = captured["inspect"](session_id=sid)

    assert result.is_error is True
    assert result.structured_content["ok"] is False
    assert result.structured_content["error"]["code"] == "script_error"
    assert result.structured_content["error"]["message"] == "boom"
