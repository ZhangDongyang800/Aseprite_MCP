"""inspect must not hand back an image bigger than the preview budget."""

import json

from fastmcp.tools import ToolResult
from PIL import Image as PILImage

BASE_META = {"width": 4096, "height": 4096, "frames": [], "layers": [], "palette": [], "tags": []}


def _runner_with(meta: dict):
    def run_script(script, params):
        PILImage.new("RGBA", (8, 8), (0, 0, 0, 0)).save(params["output"])
        PILImage.new("RGBA", (8, 8), (0, 0, 0, 0)).save(params["metrics_output"])
        return {"success": True, "stdout": json.dumps(meta), "stderr": ""}
    return run_script


def test_inspect_reports_when_the_preview_was_downscaled(tools):
    captured, sm, runner = tools
    sid = sm.create_session(64, 64)
    runner.run_script.side_effect = _runner_with(dict(BASE_META, scale=1, scale_clamped=True))

    result = captured["inspect"](session_id=sid, scale=4)

    assert isinstance(result, ToolResult)
    warnings = result.structured_content["warnings"]
    assert warnings and "budget" in warnings[0]


def test_inspect_is_silent_when_the_scale_is_honoured(tools):
    captured, sm, runner = tools
    sid = sm.create_session(64, 64)
    runner.run_script.side_effect = _runner_with(dict(BASE_META, scale=4, scale_clamped=False))

    result = captured["inspect"](session_id=sid, scale=4)

    assert "warnings" not in result.structured_content