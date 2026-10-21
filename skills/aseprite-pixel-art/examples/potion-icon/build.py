#!/usr/bin/env python3
"""Reproduce the 16x16 potion icon through a real Aseprite MCP server.

From the repository root:
    python skills/aseprite-pixel-art/examples/potion-icon/build.py

The script starts its own stdio server, writes scratch state under .build/, and delivers
potion.ase, icon.png and icon@4x.png next to this file. Requires ASEPRITE_PATH (or a
normally installed Aseprite) and the repo's Python environment with fastmcp + Pillow.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILD = HERE / ".build"
WORK = BUILD / "work"
PIXELQA = ROOT / "skills" / "aseprite-pixel-art" / "scripts" / "pixelqa.py"


async def main() -> None:
    # The source of truth is the Python model; regenerate the grid before every build.
    gen = subprocess.run([sys.executable, str(HERE / "potion.py")],
                         cwd=str(HERE), capture_output=True, text=True)
    assert gen.returncode == 0, gen.stdout + gen.stderr
    shutil.rmtree(BUILD, ignore_errors=True)

    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    env = {**os.environ, "ASEPRITE_WORK_DIR": str(WORK), "ASEPRITE_MCP_MODE": "cli"}
    transport = StdioTransport(
        command=sys.executable, args=[str(ROOT / "server.py")], env=env, cwd=str(ROOT)
    )

    async with Client(transport) as client:
        result = (await client.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": 16, "height": 16, "color_mode": "rgb"}
        ]})).structured_content
        assert result and result["ok"], result
        sid = result["session_id"]

        # Keep the grid inside the session directory: no confirmation gate for paint_grid.
        session_dir = WORK / "sessions" / sid
        grid = session_dir / "potion.lua"
        shutil.copy2(HERE / "potion.lua", grid)

        result = (await client.call_tool("apply_operations", {
            "session_id": sid,
            "ops": [
                {"op": "paint_grid", "path": str(grid)},
                {"op": "save_sprite", "path": str(HERE / "potion.ase")},
            ],
        })).structured_content
        assert result and result["ok"], result

        inspected = (await client.call_tool("inspect", {
            "session_id": sid, "frame": 1, "scale": 1,
        })).structured_content
        assert inspected and inspected["ok"], inspected
        metrics = inspected["metrics"]

        result = (await client.call_tool("apply_operations", {
            "session_id": sid,
            "ops": [
                {"op": "export", "format": "png", "output": str(HERE / "icon.png"),
                 "scale": 1, "frame": 1},
                {"op": "export", "format": "png", "output": str(HERE / "icon@4x.png"),
                 "scale": 4, "frame": 1},
            ],
        })).structured_content
        assert result and result["ok"], result

        qa_grid = subprocess.run(
            [sys.executable, str(PIXELQA), "grid", str(HERE / "potion.lua"),
             "--min-margin", "1", "--expect", "16", "16", "--max-colors", "12"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        qa_png = subprocess.run(
            [sys.executable, str(PIXELQA), "frames", str(HERE / "icon.png"),
             "--min-margin", "1", "--max-colors", "12"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        assert qa_grid.returncode == 0, qa_grid.stdout + qa_grid.stderr
        assert qa_png.returncode == 0, qa_png.stdout + qa_png.stderr

        await client.call_tool("apply_operations", {
            "session_id": sid, "confirmed": True,
            "ops": [{"op": "close_session"}],
        })

    summary = {
        "asset": "potion icon",
        "qa_generated": date.today().isoformat(),
        "canvas": [metrics["width"], metrics["height"]],
        "bbox": metrics["bbox"],
        "coverage": metrics["coverage"],
        "color_count": metrics["color_count"],
        "palette": metrics["palette"],
        "semi_transparent_pixels": metrics["semi_transparent_pixels"],
        "isolated_pixels": metrics["isolated_pixels"],
        "near_duplicate_colors": metrics["near_duplicate_colors"],
        "deliverables": ["potion.ase", "icon.png", "icon@4x.png"],
        "qa": "pixelqa grid + frames: PASS",
    }
    (HERE / "qa.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
