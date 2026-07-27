"""工具辅助函数。

提供参数验证、脚本执行封装、JSON 解析等公共工具。
"""

import json
import re
from typing import Optional, Tuple


# 十六进制颜色正则：#RRGGBB
_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_color(color: str) -> str:
    """验证十六进制颜色格式。

    Args:
        color: 颜色字符串，如 "#FF0000"

    Returns:
        大写的颜色字符串，如 "#FF0000"

    Raises:
        ValueError: 格式不合法时抛出
    """
    if not color or not _COLOR_PATTERN.match(color):
        raise ValueError(
            f"Invalid color format: {color!r}. Expected #RRGGBB (e.g. #FF0000)"
        )
    return color.upper()


def validate_session_id(session_id: Optional[str]) -> str:
    """验证 session_id 非空。

    Args:
        session_id: 会话 ID

    Returns:
        验证通过的 session_id

    Raises:
        ValueError: session_id 为空时抛出
    """
    if not session_id:
        raise ValueError("session_id is required")
    return session_id


def run_script_with_file(
    runner,
    session_manager,
    session_id: str,
    script_name: str,
    params: dict,
    layer: Optional[int] = None,
    frame: Optional[int] = None,
    error_label: str = "Operation failed",
) -> dict:
    """执行 Lua 脚本并返回标准化成功/失败字典。

    自动注入 file 参数；layer/frame 可选注入。供各 tools 模块复用，
    消除 _run_xxx_script 样板。

    Args:
        runner: Aseprite 执行器（AsepriteRunner 或 WebSocketRunner）
        session_manager: 会话管理器
        session_id: 会话 ID
        script_name: Lua 脚本文件名（如 "draw_pixel.lua"）
        params: 脚本参数（不含 file/layer/frame，本函数会自动注入）
        layer: 目标图层索引（1-based，None 则不注入）
        frame: 目标帧索引（1-based，None 则不注入）
        error_label: 脚本执行失败时的默认错误信息

    Returns:
        成功: {"success": True, "message": "<stdout>"}
        失败: {"success": False, "error": "...", "stderr": "..."}
    """
    validate_session_id(session_id)
    ase_path = session_manager.get_ase_path(session_id)

    # 注入公共参数：file 总是注入，layer/frame 可选
    all_params: dict = {"file": str(ase_path)}
    if layer is not None:
        all_params["layer"] = str(layer)
    if frame is not None:
        all_params["frame"] = str(frame)
    all_params.update(params)

    result = runner.run_script(script_name, all_params)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", error_label),
            "stderr": result.get("stderr", ""),
        }
    return {"success": True, "message": result.get("stdout", "").strip()}


def parse_json_output(
    result: dict, error_label: str = "Failed to get info"
) -> Tuple[Optional[dict], Optional[dict]]:
    """解析 runner.run_script 返回的 stdout 为 JSON。

    处理三种失败：脚本执行失败、JSON 解析失败、脚本内部 error 字段。
    供 get_pixel_color / get_palette / get_layer_info 等查询类工具复用。

    Args:
        result: runner.run_script 的返回值
        error_label: 脚本执行失败时的默认错误信息

    Returns:
        (data, error_dict) 元组：
        - 成功: (data, None)，data 是解析后的 JSON 字典
        - 失败: (None, {"success": False, "error": "...", "stderr": "..."})
    """
    if not result["success"]:
        return None, {
            "success": False,
            "error": result.get("error", error_label),
            "stderr": result.get("stderr", ""),
        }
    try:
        data = json.loads(result["stdout"].strip())
        if "error" in data:
            return None, {"success": False, "error": data["error"]}
        return data, None
    except json.JSONDecodeError:
        return None, {
            "success": False,
            "error": f"Failed to parse response: {result['stdout']}",
        }
