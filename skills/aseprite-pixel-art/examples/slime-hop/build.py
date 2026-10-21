#!/usr/bin/env python3
"""Reproduce the 32x32, 8-frame moss-slime hop through a real Aseprite MCP server.

From the repository root:
    python skills/aseprite-pixel-art/examples/slime-hop/build.py

The script regenerates frames/*.lua from slime.py, builds the document in one atomic batch,
inspects every frame, exports frame PNGs + GIFs + a sheet, and runs pixelqa. Scratch state
lives in .build/; deliverables are written next to this file.
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
EXPORT = HERE / "export"
PIXELQA = ROOT / "skills" / "aseprite-pixel-art" / "scripts" / "pixelqa.py"

FRAMES = 8
DURATIONS = [0.14, 0.10, 0.08, 0.08, 0.11, 0.09, 0.07, 0.13]
DURATIONS_MS = ",".join(str(round(d * 1000)) for d in DURATIONS)
TAG = "hop"


def grid_paths():
    names = ["neutral", "anticipate", "launch", "rise", "apex", "fall", "land", "recover"]
    return [HERE / "frames" / f"frame_{i:02d}_{name}.lua" for i, name in enumerate(names, 1)]


async def main() -> None:
    gen = subprocess.run([sys.executable, str(HERE / "slime.py")],
                         cwd=str(HERE), capture_output=True, text=True)
    assert gen.returncode == 0, gen.stdout + gen.stderr
    shutil.rmtree(WORK, ignore_errors=True)
    EXPORT.mkdir(exist_ok=True)
    for stale in EXPORT.glob("frame*.png"):
        stale.unlink()

    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    env = {**os.environ, "ASEPRITE_WORK_DIR": str(WORK), "ASEPRITE_MCP_MODE": "cli"}
    transport = StdioTransport(
        command=sys.executable, args=[str(ROOT / "server.py")], env=env, cwd=str(ROOT)
    )

    async with Client(transport) as client:
        result = (await client.call_tool("apply_operations", {"ops": [
            {"op": "create_sprite", "width": 32, "height": 32, "color_mode": "rgb"}
        ]})).structured_content
        assert result and result["ok"], result
        sid = result["session_id"]

        session_dir = WORK / "sessions" / sid
        local = {}
        for src in grid_paths():
            dst = session_dir / src.name
            shutil.copy2(src, dst)
            local[src.name] = dst

        ops = [{"op": "add_frames", "count": FRAMES - 1, "duration": 0.1}]
        ops += [{"op": "paint_grid", "path": str(local[p.name]), "frame": i}
                for i, p in enumerate(grid_paths(), 1)]
        ops += [{"op": "set_durations", "durations": DURATIONS}]
        ops += [{"op": "add_tag", "name": TAG, "from_frame": 1, "to_frame": FRAMES}]
        ops += [{"op": "save_sprite", "path": str(HERE / "slime_hop.ase")}]

        result = (await client.call_tool("apply_operations", {
            "session_id": sid, "ops": ops,
        })).structured_content
        assert result and result["ok"], result

        frame_metrics = []
        for frame in range(1, FRAMES + 1):
            inspected = (await client.call_tool("inspect", {
                "session_id": sid, "frame": frame, "scale": 1,
            })).structured_content
            assert inspected and inspected["ok"], inspected
            meta, metrics = inspected["meta"], inspected["metrics"]
            assert meta["frames_total"] == FRAMES, meta
            assert len(meta["tags"]) == 1 and meta["tags"][0]["name"] == TAG, meta
            got = [round(f["duration"], 3) for f in meta["frames"]]
            assert got == [round(d, 3) for d in DURATIONS], got
            assert metrics["semi_transparent_pixels"] == 0, metrics
            assert metrics["isolated_pixels"] == 0, metrics
            assert metrics["near_duplicate_colors"] == [], metrics
            assert metrics["color_count"] <= 16, metrics
            bbox = metrics["bbox"]
            assert bbox, metrics
            assert bbox["x"] >= 1 and bbox["y"] >= 1, bbox
            assert bbox["x"] + bbox["width"] <= 31, bbox
            assert bbox["y"] + bbox["height"] <= 31, bbox
            frame_metrics.append({
                "frame": frame, "bbox": bbox, "coverage": metrics["coverage"],
                "colors": metrics["color_count"], "opaque": round(
                    metrics["coverage"] * metrics["width"] * metrics["height"]),
            })

        result = (await client.call_tool("apply_operations", {
            "session_id": sid,
            "ops": [
                {"op": "export", "format": "frames",
                 "output": str(EXPORT / "frame.png")},
                {"op": "export", "format": "gif",
                 "output": str(EXPORT / "slime_hop.gif"), "scale": 1},
                {"op": "export", "format": "gif",
                 "output": str(EXPORT / "slime_hop@4x.gif"), "scale": 4},
                {"op": "export", "format": "sheet",
                 "output": str(EXPORT / "slime_hop_sheet.png"),
                 "layout": "rows", "columns": 4, "padding": 0},
            ],
        })).structured_content
        assert result and result["ok"], result
        missing = [f"frame{i}.png" for i in range(1, FRAMES + 1)
                   if not (EXPORT / f"frame{i}.png").is_file()]
        assert not missing, missing

        qa_cmds = {
            "grid": [sys.executable, str(PIXELQA), "grid",
                     *[str(p) for p in grid_paths()],
                     "--min-margin", "1", "--loop", "--expect", "32", "32"],
            "frames": [sys.executable, str(PIXELQA), "frames",
                       str(EXPORT / "frame*.png"), "--min-margin", "1", "--loop",
                       "--max-colors", "16", "--max-mass-ratio", "1.6"],
            "gif": [sys.executable, str(PIXELQA), "gif",
                    str(EXPORT / "slime_hop.gif"), "--expect-frames", str(FRAMES),
                    "--expect-durations", DURATIONS_MS],
            "sheet": [sys.executable, str(PIXELQA), "sheet",
                      str(EXPORT / "slime_hop_sheet.png"), "--cell", "32x32",
                      "--columns", "4", "--frames", str(EXPORT / "frame*.png")],
            "contact": [sys.executable, str(PIXELQA), "contact",
                        str(EXPORT / "frame*.png"), "--out", str(EXPORT / "contact.png"),
                        "--scale", "8", "--columns", "4", "--bg", "dark", "--labels"],
        }
        qa_results = {}
        for name, cmd in qa_cmds.items():
            run = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            assert run.returncode == 0, f"{name} QA failed:\n{run.stdout}\n{run.stderr}"
            qa_results[name] = json.loads(run.stdout)

        await client.call_tool("apply_operations", {
            "session_id": sid, "confirmed": True,
            "ops": [{"op": "close_session"}],
        })

    frames_qa = qa_results["frames"]
    summary = {
        "asset": "moss slime hop",
        "qa_generated": date.today().isoformat(),
        "canvas": [32, 32],
        "frames": frame_metrics,
        "durations_ms": [round(d * 1000) for d in DURATIONS],
        "tag": TAG,
        "diffs": [(d["changed_pixels"], d["bbox"]) for d in frames_qa["diffs"]],
        "loop": frames_qa["loop"],
        "mass_ratio": frames_qa["ratios"]["mass_max_min"],
        "gif": {"frames": len(qa_results["gif"]["frames"]),
                "durations_ms": qa_results["gif"]["durations_ms"]},
        "sheet": {"size": qa_results["sheet"]["size"],
                  "all_cells_match": all(c.get("matches_frame_file") for c in qa_results["sheet"]["cells"])},
        "deliverables": ["slime_hop.ase", "export/frame1-8.png",
                         "export/slime_hop.gif", "export/slime_hop@4x.gif",
                         "export/slime_hop_sheet.png", "export/contact.png"],
        "qa": "grid + frames + gif + sheet: PASS",
    }
    (HERE / "qa.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
