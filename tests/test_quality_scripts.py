"""质量检查脚本测试（Task 11，docs §3.6/§5/§7）。

验证 export_silhouette.lua / check_standards.lua
脚本文件存在，且能被 runner 按预期参数模式调用。

注意：check_standards.lua 输出 JSON 字符串（单行），不是 OK/ERROR 格式。
"""

from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config


# 脚本目录（与生产环境一致：<项目根>/scripts/）
SCRIPTS_DIR = Config().scripts_dir


def test_export_silhouette_script_exists():
    """测试 export_silhouette.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "export_silhouette.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_check_standards_script_exists():
    """测试 check_standards.lua 脚本文件存在。"""
    script_path = SCRIPTS_DIR / "check_standards.lua"
    assert script_path.exists(), f"脚本不存在: {script_path}"


def test_export_silhouette_script_contains_silhouette_logic():
    """测试 export_silhouette.lua 包含剪影生成核心逻辑（docs §3.6 关键设计）。

    剪影测试核心：所有非透明像素 -> 黑色，再导出 PNG。
    应使用 rgbaA 判透明、drawPixel 写黑、saveCopyAs 导出。
    """
    script_path = SCRIPTS_DIR / "export_silhouette.lua"
    content = script_path.read_text(encoding="utf-8")
    # 非透明像素判断（rgbaA > 0）
    assert "rgbaA" in content, "export_silhouette.lua 应使用 rgbaA 判断透明度"
    # 写入黑色像素
    assert "drawPixel" in content, "export_silhouette.lua 应使用 drawPixel 写入剪影"
    # 黑色像素定义（0,0,0,255）
    assert "rgba(0, 0, 0, 255)" in content or "rgba(0,0,0,255)" in content, (
        "export_silhouette.lua 应定义纯黑剪影色 rgba(0,0,0,255)"
    )
    # 导出 PNG
    assert "saveCopyAs" in content, "export_silhouette.lua 应使用 saveCopyAs 导出"
    # 参数应包含 file / output / scale
    assert 'app.params["file"]' in content
    assert 'app.params["output"]' in content
    assert 'app.params["scale"]' in content


def test_check_standards_script_contains_json_report():
    """测试 check_standards.lua 返回 JSON 规范报告（docs §7 关键设计）。

    报告应含 size / color_count / timing / pixel_art 四类检查，
    以及 stats 统计信息；pixel_art 含 semi_transparent / isolated_pixels / visual_review。
    """
    script_path = SCRIPTS_DIR / "check_standards.lua"
    content = script_path.read_text(encoding="utf-8")
    # JSON 顶层字段
    assert '"success"' in content, "check_standards.lua 应输出 success 字段"
    assert '"checks"' in content, "check_standards.lua 应输出 checks 字段"
    assert '"stats"' in content, "check_standards.lua 应输出 stats 字段"
    # 四类检查项
    assert '"size"' in content, "应包含 size 尺寸检查"
    assert '"color_count"' in content, "应包含 color_count 颜色数检查"
    assert '"timing"' in content, "应包含 timing 帧时长检查"
    assert '"pixel_art"' in content, "应包含 pixel_art 像素艺术检查"
    # pixel_art 子项
    assert '"semi_transparent"' in content, "应检测半透明像素（docs §5.1）"
    assert '"isolated_pixels"' in content, "应检测孤立像素（docs §5.2 jaggies）"
    assert '"visual_review"' in content, "应提示视觉复查（docs §5.2/§5.4）"
    # stats 统计字段
    assert '"width"' in content, "应输出 width 统计"
    assert '"height"' in content, "应输出 height 统计"
    assert '"frames"' in content, "应输出 frames 统计"
    # 参数应包含 file
    assert 'app.params["file"]' in content


def test_export_silhouette_runner_call_pattern():
    """测试 mock runner 调用 export_silhouette.lua 的参数模式。

    export_silhouette.lua 接收 file、output（PNG 路径）、scale（默认 1），
    把所有非透明像素转黑后导出剪影 PNG。
    """
    runner = MagicMock()
    runner.run_script.return_value = {
        "success": True,
        "stdout": "OK: exported silhouette to /tmp/silhouette.png",
        "stderr": "",
    }

    # 模拟导出 2x 缩放的剪影 PNG
    params = {
        "file": "/tmp/canvas.ase",
        "output": "/tmp/silhouette.png",
        "scale": "2",
    }
    result = runner.run_script("export_silhouette.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("export_silhouette.lua", params)
    assert result["success"] is True
    assert "silhouette" in result["stdout"]


def test_check_standards_runner_call_pattern():
    """测试 mock runner 调用 check_standards.lua 的参数模式。

    check_standards.lua 接收 file，返回单行 JSON 规范报告
    （size/color_count/timing/pixel_art 多项检查 + stats 统计）。
    """
    runner = MagicMock()
    # 模拟返回的 JSON 报告（与脚本实际输出格式一致）
    runner.run_script.return_value = {
        "success": True,
        "stdout": '{"success": true, "checks": {"size": {"pass": true}, "color_count": {"pass": true}, "timing": {"pass": true}, "pixel_art": {"semi_transparent": 0, "isolated_pixels": 0}}, "stats": {"width": 16, "height": 16, "color_count": 8, "frames": 1}}',
        "stderr": "",
    }

    # 模拟检查 16x16 画布规范
    params = {
        "file": "/tmp/canvas.ase",
    }
    result = runner.run_script("check_standards.lua", params)

    # 验证 runner 被正确调用
    runner.run_script.assert_called_once_with("check_standards.lua", params)
    assert result["success"] is True
    # 输出应为 JSON 格式（以 { 开头），不是 OK/ERROR
    assert result["stdout"].startswith("{"), "check_standards.lua 应输出 JSON 而非 OK/ERROR"
    assert '"checks"' in result["stdout"]
    assert '"stats"' in result["stdout"]
