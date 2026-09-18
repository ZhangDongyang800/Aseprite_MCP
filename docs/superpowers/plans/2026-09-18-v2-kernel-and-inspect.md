# Aseprite MCP v2 · 内核与感知（阶段 0-2）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 75 个工具收敛为 3 个（`apply_operations` / `inspect` / `run_lua`），变更走单进程单事务、真实 undo/redo，感知走安全只读的 `inspect`。

**Architecture:** Python 侧 `src/v2/` 提供 op 注册表、Lua 编译器、结果信封与执行器；`ops[]` 被编译成一段临时 Lua 程序，在一个 `aseprite -b` 进程内、一个 `app.transaction()` 中执行。感知由静态 `scripts/inspect.lua` 在临时副本上导出并用 PIL 计算指标。

**Tech Stack:** Python 3.10+、FastMCP 4、Pydantic 2、Pillow、pytest。

**Spec:** `docs/superpowers/specs/2026-09-18-aseprite-mcp-v2-design.md`

## Global Constraints

- FastMCP 固定 `>=4.0.2,<5`（spec §4）。
- 工具面恰好 3 个：`apply_operations`、`inspect`、`run_lua`（spec §5）。
- 所有工具返回统一信封；运行期失败不抛异常（spec §7）。
- 会话生命周期是 op，不是工具（spec §5）。
- CLI undo 单级、Live 原生；无备份时返回 `no_more_undo`/`no_more_redo`，禁止假成功（spec §6.3）。
- `inspect` 永不改动活动文档，只在临时副本上缩放（spec §8、P0-1）。
- 层/帧索引 **1-based**；颜色 `#RRGGBB`；Lua 无 `loadstring`，参数以 Python 序列化的 Lua 字面量嵌入（spec §6.2）。
- 每会话一把锁，固定 `<work_dir>/_batch.lua`（spec §6.4）。
- 现有 247 个测试在阶段 0 必须保持通过；随旧模块退役逐步删除（spec §11）。
- 提交步骤：仅当用户已授权时才执行 `git commit`；未授权则跳过提交、保留工作区改动。

---

### Task 0.1: 升级 FastMCP 4 并恢复基线

**Files:**
- Modify: `pyproject.toml:7`
- Test: `tests/test_server.py`（仅在 API 变动导致失败时修改）

**Interfaces:**
- Consumes: 无
- Produces: 可用的 FastMCP 4 环境；后续所有任务依赖。

- [ ] **Step 1: 改依赖**

`pyproject.toml` 的 `dependencies` 中 `"fastmcp>=2.0.0"` 改为：

```toml
    "fastmcp>=4.0.2,<5",
```

- [ ] **Step 2: 安装并确认版本**

Run:
```bash
pip install -e ".[dev]"
python -c "import importlib.metadata as m; print(m.version('fastmcp'))"
```
Expected: 输出 `4.0.x`。

- [ ] **Step 3: 验证本仓用到的 FastMCP 符号仍存在**

Run:
```bash
python -c "from fastmcp import FastMCP; from fastmcp.utilities.types import Image; print('OK')"
```
Expected: `OK`。若 `Image` 导入失败，执行 `python -c "import fastmcp.utilities.types as t; print([n for n in dir(t) if 'mage' in n])"` 找到新位置并更新全部 5 处导入：`src/tools/animation_tools.py:7`、`src/tools/import_tools.py:8`、`src/tools/inspect_tools.py:9`、`src/tools/quality_tools.py:8`、`src/tools/tileset_tools.py:6`。

- [ ] **Step 4: 跑全量测试**

Run: `pytest -m "not e2e" -q`
Expected: 全部通过。此任务不做重构；任何失败只做兼容性最小修复并在此记录一句原因：

```
例：test_server.py::test_tool_count 失败 → 改为断言 3 个 v2 工具（Task 1.9 处理）
```

- [ ] **Step 5: 提交（若已授权）**

```bash
git add pyproject.toml
git commit -m "chore: upgrade fastmcp to 4.x"
```

---

### Task 0.2: 验证 FastMCP 4 的"图片 + 结构化"同返与注解 API

**Files:**
- Create: `tests/v2/test_fastmcp_capabilities.py`
- Create: `src/v2/__init__.py`（空文件，声明包）

**Interfaces:**
- Consumes: Task 0.1
- Produces: 确定的返回类型选择——`inspect` 任务据此实现（Task 2.2 使用 `IMAGE_STRUCTURED_MODE` 常量）。

- [ ] **Step 1: 写能力探测测试**

```python
"""探测 FastMCP 4 实际提供的 API，避免凭记忆编码。"""
import inspect as pyinspect

import fastmcp
from fastmcp import FastMCP


def test_tool_decorator_accepts_annotations():
    mcp = FastMCP("probe")

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def _probe(x: int) -> dict:
        return {"x": x}

    assert callable(_probe)


def test_result_types_available():
    """ToolResult / ImageContent 至少一种可用于“图片+结构化”。"""
    names = set(dir(fastmcp))
    found = sorted(n for n in names if "Result" in n or "Content" in n)
    assert found, "fastmcp 顶层无可用的 Result/Content 类型"


def test_image_import_path():
    from fastmcp.utilities.types import Image  # noqa: F401
    assert pyinspect.isclass(Image)
```

- [ ] **Step 2: 运行并据实修正**

Run: `pytest tests/v2/test_fastmcp_capabilities.py -v`
Expected: PASS。若 `test_result_types_available` 失败，执行：

```bash
python -c "import fastmcp, pkgutil; [print(m.name) for m in pkgutil.iter_modules(fastmcp.__path__)]"
python -c "import fastmcp; print([n for n in dir(fastmcp)])"
```

把真实可用的联合返回方式（例如 `fastmcp.tools.ToolResult` 或 `from fastmcp.server.context import Context`）写进测试断言。

- [ ] **Step 3: 在包内固化选择**

`src/v2/__init__.py`：

```python
"""Aseprite MCP v2 内核包。"""

# 由 Task 0.2 的探测结论决定；默认单载荷（图片），
# 若 @mcp.tool 返回 ToolResult 可用则改为 "tool_result"。
IMAGE_STRUCTURED_MODE = "image_only"
```

若探测证明可同返，则改为 `IMAGE_STRUCTURED_MODE = "tool_result"`，并在 `tests/v2/test_fastmcp_capabilities.py` 增加对应断言。

- [ ] **Step 4: 提交（若已授权）**

```bash
git add src/v2/__init__.py tests/v2/test_fastmcp_capabilities.py
git commit -m "test: probe fastmcp 4 capabilities"
```

---

### Task 0.3: Aseprite 路径自动探测

**Files:**
- Modify: `src/config.py:46-50`
- Modify: `tests/test_config.py`（新增用例；保留原有断言）
- Create: `src/aseprite_locate.py`

**Interfaces:**
- Consumes: 无
- Produces: `src.aseprite_locate.locate_aseprite() -> str | None`；`Config.aseprite_path` 使用探测结果。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_config.py`：

```python
def test_locate_prefers_env(monkeypatch, tmp_path):
    from src.aseprite_locate import locate_aseprite

    fake = tmp_path / "aseprite.exe"
    fake.write_text("x")
    monkeypatch.setenv("ASEPRITE_PATH", str(fake))
    assert locate_aseprite() == str(fake)


def test_locate_returns_none_when_missing(monkeypatch, tmp_path):
    from src.aseprite_locate import locate_aseprite

    monkeypatch.setenv("ASEPRITE_PATH", str(tmp_path / "nope.exe"))
    monkeypatch.setattr(
        "src.aseprite_locate._candidate_paths", lambda: [tmp_path / "nope2.exe"]
    )
    assert locate_aseprite() is None
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_config.py::test_locate_prefers_env tests/test_config.py::test_locate_returns_none_when_missing -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.aseprite_locate'`。

- [ ] **Step 3: 实现探测**

`src/aseprite_locate.py`：

```python
"""跨平台定位 Aseprite 可执行文件。"""

import os
import shutil
import sys
from pathlib import Path


def _candidate_paths() -> list[Path]:
    home = Path.home()
    if sys.platform == "win32":
        return [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Aseprite" / "aseprite.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Aseprite" / "aseprite.exe",
            Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "Aseprite" / "aseprite.exe",
            Path("C:/Program Files (x86)/Steam/steamapps/common/Aseprite/aseprite.exe"),
            Path("D:/Steam/steamapps/common/Aseprite/aseprite.exe"),
            Path("D:/SteamLibrary/steamapps/common/Aseprite/aseprite.exe"),
        ]
    if sys.platform == "darwin":
        return [
            Path("/Applications/Aseprite.app/Contents/MacOS/aseprite"),
            home / "Applications" / "Aseprite.app" / "Contents" / "MacOS" / "aseprite",
        ]
    return [
        Path("/usr/bin/aseprite"),
        Path("/usr/local/bin/aseprite"),
        home / ".local" / "bin" / "aseprite",
        Path("/snap/bin/aseprite"),
    ]


def locate_aseprite() -> str | None:
    """返回可执行文件路径；优先 ASEPRITE_PATH，然后 PATH，最后常见安装位置。"""
    env = os.environ.get("ASEPRITE_PATH")
    if env and Path(env).exists():
        return env
    found = shutil.which("aseprite") or shutil.which("aseprite.exe")
    if found:
        return found
    for candidate in _candidate_paths():
        if candidate.exists():
            return str(candidate)
    return None
```

- [ ] **Step 4: 接入 Config**

`src/config.py` 第 46-50 行改为：

```python
        if self.aseprite_path is None:
            from src.aseprite_locate import locate_aseprite

            self.aseprite_path = (
                os.environ.get("ASEPRITE_PATH")
                or locate_aseprite()
                or "aseprite"
            )
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_config.py -q`
Expected: PASS。

- [ ] **Step 6: 提交（若已授权）**

```bash
git add src/aseprite_locate.py src/config.py tests/test_config.py
git commit -m "feat: auto-detect aseprite executable"
```

---

### Task 1.1: 结果信封与错误分类

**Files:**
- Create: `src/v2/result.py`
- Test: `tests/v2/test_result.py`

**Interfaces:**
- Consumes: 无
- Produces: `ErrorCode`、`ErrorInfo`、`OpResult`、`Artifact`、`UndoInfo`、`Envelope`；`Envelope.failure(code, message, *, hint="", op_index=None) -> Envelope`。

- [ ] **Step 1: 写失败测试**

```python
from src.v2.result import Envelope, ErrorCode, ErrorInfo, OpResult, UndoInfo


def test_failure_envelope_shape():
    env = Envelope.failure(
        ErrorCode.INVALID_ARGS, "bad op", hint="known ops: draw_rect", op_index=2
    )
    assert env.ok is False
    assert env.changed is False
    assert env.error is not None
    assert env.error.code == ErrorCode.INVALID_ARGS
    assert env.error.op_index == 2
    assert env.undo.available is False
    assert env.model_dump()["error"]["code"] == "invalid_args"


def test_success_envelope_roundtrip():
    env = Envelope(
        ok=True,
        session_id="s1",
        mode="cli",
        op_results=[OpResult(op="draw_rect", ok=True, data={"drawn": 1})],
        changed=True,
        undo=UndoInfo(mode="file_backup", available=True),
    )
    dumped = env.model_dump()
    assert dumped["op_results"][0]["op"] == "draw_rect"
    assert Envelope.model_validate(dumped).ok is True
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_result.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.v2.result'`。

- [ ] **Step 3: 实现**

```python
"""统一结果信封与稳定错误分类（spec §7）。"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    INVALID_ARGS = "invalid_args"
    SESSION_NOT_FOUND = "session_not_found"
    ASEPRITE_NOT_FOUND = "aseprite_not_found"
    UNSUPPORTED_IN_MODE = "unsupported_in_mode"
    OP_FAILED = "op_failed"
    SCRIPT_ERROR = "script_error"
    LUA_RUNTIME_ERROR = "lua_runtime_error"
    FILE_ERROR = "file_error"
    NO_MORE_UNDO = "no_more_undo"
    NO_MORE_REDO = "no_more_redo"
    CONFIRMATION_REQUIRED = "confirmation_required"


class ErrorInfo(BaseModel):
    code: ErrorCode
    message: str
    hint: str = ""
    op_index: Optional[int] = None


class OpResult(BaseModel):
    op: str
    ok: bool
    data: Any = None


class Artifact(BaseModel):
    kind: Literal["png", "gif", "json", "ase"]
    path: str
    role: str


class UndoInfo(BaseModel):
    mode: Literal["transaction", "file_backup"] = "file_backup"
    available: bool = False


class Envelope(BaseModel):
    ok: bool
    session_id: Optional[str] = None
    mode: Literal["cli", "ws"] = "cli"
    op_results: list[OpResult] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    changed: bool = False
    undo: UndoInfo = Field(default_factory=UndoInfo)
    timing_ms: int = 0
    error: Optional[ErrorInfo] = None

    @classmethod
    def failure(
        cls,
        code: ErrorCode,
        message: str,
        *,
        hint: str = "",
        op_index: Optional[int] = None,
        session_id: Optional[str] = None,
        mode: str = "cli",
        op_results: Optional[list[OpResult]] = None,
    ) -> "Envelope":
        return cls(
            ok=False,
            session_id=session_id,
            mode=mode,
            op_results=op_results or [],
            changed=False,
            undo=UndoInfo(),
            error=ErrorInfo(code=code, message=message, hint=hint, op_index=op_index),
        )
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/v2/test_result.py -q`
Expected: PASS。

- [ ] **Step 5: 提交（若已授权）**

```bash
git add src/v2/result.py tests/v2/test_result.py
git commit -m "feat(v2): result envelope and error taxonomy"
```

---

### Task 1.2: Op 注册表与参数校验

**Files:**
- Create: `src/v2/registry.py`
- Test: `tests/v2/test_registry.py`

**Interfaces:**
- Consumes: `src.v2.result.ErrorCode/ErrorInfo`
- Produces: `OpSpec`、`OpRegistry`、`REGISTRY`；`OpRegistry.validate(raw_ops) -> tuple[list[tuple[OpSpec, BaseModel]], Optional[ErrorInfo]]`；`OpRegistry.catalog() -> list[dict]`。

- [ ] **Step 1: 写失败测试**

```python
from pydantic import BaseModel

from src.v2.registry import OpRegistry, OpSpec
from src.v2.result import ErrorCode


class _Params(BaseModel):
    x: int
    color: str = "#000000"


def _registry() -> OpRegistry:
    reg = OpRegistry()
    reg.register(OpSpec(name="draw_pixel", category="draw", params=_Params, mutating=True))
    return reg


def test_validate_ok():
    reg = _registry()
    parsed, err = reg.validate([{"op": "draw_pixel", "x": 1}])
    assert err is None
    assert parsed[0][0].name == "draw_pixel"
    assert parsed[0][1].x == 1


def test_validate_unknown_op():
    reg = _registry()
    parsed, err = reg.validate([{"op": "nope"}])
    assert parsed == []
    assert err is not None and err.code == ErrorCode.INVALID_ARGS
    assert err.op_index == 0


def test_validate_bad_params_reports_index():
    reg = _registry()
    parsed, err = reg.validate(
        [{"op": "draw_pixel", "x": 1}, {"op": "draw_pixel", "x": "not-an-int"}]
    )
    assert err is not None and err.op_index == 1


def test_duplicate_registration_rejected():
    reg = _registry()
    try:
        reg.register(OpSpec(name="draw_pixel", category="draw", params=_Params))
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_catalog_is_json_schema_serializable():
    reg = _registry()
    catalog = reg.catalog()
    assert catalog[0]["name"] == "draw_pixel"
    assert catalog[0]["schema"]["properties"]["x"]["type"] == "integer"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_registry.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现**

```python
"""Op 注册表：单一事实来源（spec §6.1）。"""

from dataclasses import dataclass
from typing import Callable, Optional, Type

from pydantic import BaseModel, ValidationError

from src.v2.result import ErrorCode, ErrorInfo


@dataclass
class OpSpec:
    name: str
    category: str
    params: Type[BaseModel]
    result: Optional[Type[BaseModel]] = None
    backend: str = "lua"
    lua: Optional[str] = None
    mutating: bool = False
    destructive: bool = False
    cli_builder: Optional[Callable[[BaseModel], list[str]]] = None


class OpRegistry:
    def __init__(self) -> None:
        self._ops: dict[str, OpSpec] = {}

    def register(self, spec: OpSpec) -> OpSpec:
        if spec.name in self._ops:
            raise ValueError(f"duplicate op: {spec.name}")
        self._ops[spec.name] = spec
        return spec

    def get(self, name: str) -> OpSpec:
        return self._ops[name]

    def names(self) -> list[str]:
        return sorted(self._ops)

    def catalog(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "category": s.category,
                "schema": s.params.model_json_schema(),
                "mutating": s.mutating,
                "destructive": s.destructive,
                "backend": s.backend,
            }
            for s in sorted(self._ops.values(), key=lambda x: (x.category, x.name))
        ]

    def validate(
        self, raw_ops: list[dict]
    ) -> tuple[list[tuple[OpSpec, BaseModel]], Optional[ErrorInfo]]:
        parsed: list[tuple[OpSpec, BaseModel]] = []
        for i, raw in enumerate(raw_ops):
            if not isinstance(raw, dict) or "op" not in raw:
                return [], ErrorInfo(
                    code=ErrorCode.INVALID_ARGS,
                    message="each op must be an object with an 'op' key",
                    op_index=i,
                )
            name = raw["op"]
            spec = self._ops.get(name)
            if spec is None:
                return [], ErrorInfo(
                    code=ErrorCode.INVALID_ARGS,
                    message=f"unknown op: {name}",
                    hint="known: " + ", ".join(self.names()),
                    op_index=i,
                )
            payload = {k: v for k, v in raw.items() if k != "op"}
            try:
                params = spec.params.model_validate(payload)
            except ValidationError as exc:
                return [], ErrorInfo(
                    code=ErrorCode.INVALID_ARGS,
                    message=str(exc),
                    op_index=i,
                )
            parsed.append((spec, params))
        return parsed, None


REGISTRY = OpRegistry()
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/v2/test_registry.py -q`
Expected: PASS。

- [ ] **Step 5: 提交（若已授权）**

```bash
git add src/v2/registry.py tests/v2/test_registry.py
git commit -m "feat(v2): op registry with validation"
```

---

### Task 1.3: Lua 字面量序列化与编译

**Files:**
- Create: `src/v2/compile.py`
- Test: `tests/v2/test_compile.py`

**Interfaces:**
- Consumes: `OpSpec`、`BaseModel`
- Produces:
  - `lua_string(s: str) -> str`
  - `lua_value(v) -> str`
  - `compile_ops(parsed, *, file_path: Path, scripts_dir: Path, atomic: bool) -> str`
  - `parse_result_stdout(stdout: str) -> dict`（解析 `__MCP_JSON__` 标记行）

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

from pydantic import BaseModel

from src.v2.compile import compile_ops, lua_string, lua_value, parse_result_stdout
from src.v2.registry import OpSpec


class _P(BaseModel):
    x: int
    color: str


def _spec():
    return OpSpec(
        name="draw_pixel", category="draw", params=_P,
        lua="_mcp_op_draw_pixel", mutating=True,
    )


def test_lua_string_escapes_control_and_quotes():
    assert lua_string('a"b') == '"a\\"b"'
    assert lua_string("a\nb") == '"a\\nb"'
    assert lua_string("a\x01b") == '"a\\x01b"'
    assert lua_string("中文") == '"中文"'


def test_lua_value_nested():
    assert lua_value({"a": 1, "b": [True, None]}) == "{a=1,b={true,nil}}"
    assert lua_value({"not ident": "x"}) == '{["not ident"]="x"}'


def test_compile_contains_single_transaction_and_literal():
    spec = _spec()
    params = _P(x=3, color="#FF0000")
    src = compile_ops(
        [(spec, params)],
        file_path=Path("C:/w/canvas.ase"),
        scripts_dir=Path("C:/repo/scripts"),
        atomic=True,
    )
    assert "app.transaction(" in src
    assert "_mcp_op_draw_pixel" in src
    assert "{x=3,color=\"#FF0000\"}" in src
    assert src.count("app.transaction(") == 1
    assert "dofile" in src and "mcp_common.lua" in src


def test_compile_non_atomic_has_no_transaction():
    spec = _spec()
    src = compile_ops(
        [(spec, _P(x=1, color="#000000"))],
        file_path=Path("c.ase"), scripts_dir=Path("s"), atomic=False,
    )
    assert "app.transaction(" not in src


def test_parse_result_stdout():
    payload = '{\n"ops": []\n}'
    out = f"noise\n__MCP_JSON__{payload}\n"
    assert parse_result_stdout(out) == {"ops": []}
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_compile.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现**

```python
"""把 ops[] 编译成一段 Lua 程序（spec §6.2）。"""

import json
from pathlib import Path

from pydantic import BaseModel

from src.v2.registry import OpSpec

RESULT_MARKER = "__MCP_JSON__"


def lua_string(s: str) -> str:
    out = ['"']
    for ch in s:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif code < 32 or code == 127:
            out.append(f"\\x{code:02x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def lua_value(v) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"cannot serialize non-finite number: {v}")
        return repr(v)
    if isinstance(v, str):
        return lua_string(v)
    if isinstance(v, (list, tuple)):
        return "{" + ",".join(lua_value(x) for x in v) + "}"
    if isinstance(v, dict):
        parts = []
        for k, val in v.items():
            if isinstance(k, str) and k.isidentifier():
                parts.append(f"{k}={lua_value(val)}")
            else:
                parts.append(f"[{lua_value(k)}]={lua_value(val)}")
        return "{" + ",".join(parts) + "}"
    raise TypeError(f"cannot serialize {type(v)!r}")


def _op_literal(spec: OpSpec, params: BaseModel) -> str:
    return lua_value(params.model_dump(mode="json"))


_HEADER = """-- generated by aseprite-mcp v2; do not edit
if not _G._mcp_common_loaded then
  dofile({common})
end
{categories}local _file = {file}
local _results = {{}}
local _sprite = nil
local function _resolve()
  if _sprite then return _sprite end
  _sprite = _G._mcp_get_sprite(_file)
  if not _sprite then _sprite = _G._mcp_created_sprite end
  if not _sprite then error("no sprite. Call create_sprite first.") end
  return _sprite
end
local function _record(name, ok, data)
  _results[#_results + 1] = {{op=name, ok=ok, data=data}}
  return ok
end
"""

_BOOTSTRAP_OPS = {"create_sprite", "open_sprite"}

_FOOTER = """if _saved_ok then
  _mcp_maybe_save(_sprite, _file)
end
print("\\n{marker}" .. json.encode({{ops=_results, saved=_saved_ok and true or false, error=_run_error}}))
"""


def compile_ops(
    parsed: list[tuple[OpSpec, BaseModel]],
    *,
    file_path: Path,
    scripts_dir: Path,
    atomic: bool,
) -> str:
    categories = sorted({spec.category for spec, _ in parsed if spec.lua})
    cat_lines = "".join(
        f"dofile({lua_string(str(scripts_dir / ('ops_' + cat) + '.lua'))})\n"
        for cat in categories
    )
    header = _HEADER.format(
        common=lua_string(str(scripts_dir / "mcp_common.lua")),
        categories=cat_lines,
        file=lua_string(str(file_path)),
        marker=RESULT_MARKER,
    )

    calls = []
    for i, (spec, params) in enumerate(parsed, start=1):
        if spec.lua is None:
            continue  # 元 op（如 close_session）由 Python 侧处理，不生成 Lua
        target = "_resolve()"
        after = ""
        if i == 1 and spec.name in _BOOTSTRAP_OPS:
            target = "nil"
            after = "\n  _sprite = _G._mcp_created_sprite"
        calls.append(
            f"""do
  local _ok, _data = pcall({spec.lua}, {target}, {_op_literal(spec, params)})
  _record({lua_string(spec.name)}, _ok, _data){after}
  if not _ok then _saved_ok = false; _run_error = tostring(_data)"""
        )
        if atomic:
            calls.append(f'    error("MCP_OP_FAILED:{i}", 0)')
        calls.append("  end\nend\n")

    body = "".join(calls)

    if atomic:
        runner = f"""local _saved_ok = true
local _run_error = nil
local _tx_ok, _tx_err = pcall(function()
  app.transaction("MCP: {len(parsed)} ops", function()
{body}  end)
end)
if not _tx_ok then _saved_ok = false; _run_error = tostring(_tx_err) end
"""
    else:
        runner = f"""local _saved_ok = true
local _run_error = nil
{body}"""

    return header + runner + _FOOTER.format(marker=RESULT_MARKER)


def parse_result_stdout(stdout: str) -> dict:
    lines = [ln for ln in stdout.splitlines() if ln.startswith(RESULT_MARKER)]
    if not lines:
        raise ValueError(f"no {RESULT_MARKER} marker in output: {stdout!r}")
    return json.loads(lines[-1][len(RESULT_MARKER):])
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/v2/test_compile.py -q`
Expected: PASS。

- [ ] **Step 5: 提交（若已授权）**

```bash
git add src/v2/compile.py tests/v2/test_compile.py
git commit -m "feat(v2): lua literal serializer and op compiler"
```

---

### Task 1.4: Lua op 库（session + draw 第一批）

**Files:**
- Modify: `scripts/mcp_common.lua`（保留现有内容；修正 `_mcp_get_or_create_sprite` 的 Live 复用行为）
- Create: `scripts/ops_session.lua`
- Create: `scripts/ops_draw.lua`
- Test: `tests/v2/test_lua_op_files.py`

**Interfaces:**
- Consumes: 无（纯 Lua）
- Produces: 全局函数 `_mcp_op_create_sprite`、`_mcp_op_open_sprite`、`_mcp_op_save_sprite`、`_mcp_op_clear_canvas`、`_mcp_op_draw_pixel`、`_mcp_op_draw_rect`、`_mcp_op_fill_region`。签名统一为 `function(sprite, params) -> table`，返回可 JSON 序列化的表。

- [ ] **Step 1: 写文件存在与签名测试**

```python
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def test_op_libraries_exist_with_functions():
    for fname, funcs in {
        "ops_session.lua": ["_mcp_op_create_sprite", "_mcp_op_open_sprite", "_mcp_op_save_sprite"],
        "ops_draw.lua": [
            "_mcp_op_clear_canvas", "_mcp_op_draw_pixel",
            "_mcp_op_draw_rect", "_mcp_op_fill_region",
        ],
    }.items():
        text = (SCRIPTS / fname).read_text(encoding="utf-8")
        for fn in funcs:
            assert f"function _G.{fn}" in text, f"{fn} missing in {fname}"


def test_op_libraries_guard_common_load():
    for fname in ["ops_session.lua", "ops_draw.lua"]:
        text = (SCRIPTS / fname).read_text(encoding="utf-8")
        assert "_mcp_common_loaded" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_lua_op_files.py -q`
Expected: FAIL，文件不存在。

- [ ] **Step 3: 实现 `scripts/ops_session.lua`**

```lua
-- ops_session.lua：会话生命周期 op（v2 内核）
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

-- 新建文档：Live 始终新建，不复用活动 sprite（spec P0-7）
function _G._mcp_op_create_sprite(sprite, params)
    local mode = ColorMode.RGB
    if params.color_mode == "grayscale" then mode = ColorMode.GRAY
    elseif params.color_mode == "indexed" then mode = ColorMode.INDEXED end
    local created = Sprite(params.width, params.height, mode)
    if not created then error("cannot create sprite") end
    if params.file and params.file ~= "" then created:saveAs(params.file) end
    _G._mcp_created_sprite = created  -- 供生成程序引导阶段引用
    return {width = created.width, height = created.height, color_mode = params.color_mode}
end

function _G._mcp_op_save_sprite(sprite, params)
    if params.path and params.path ~= "" then
        sprite:saveAs(params.path)
        return {saved = true, path = params.path}
    end
    sprite:save()
    return {saved = true, path = sprite.filename}
end

function _G._mcp_op_open_sprite(sprite, params)
    local opened = app.open(params.path)
    if not opened then error("cannot open: " .. tostring(params.path)) end
    if params.file and params.file ~= "" then opened:saveAs(params.file) end
    _G._mcp_created_sprite = opened
    return {width = opened.width, height = opened.height, frames = #opened.frames}
end
```

- [ ] **Step 4: 实现 `scripts/ops_draw.lua`**

```lua
-- ops_draw.lua：绘制 op（v2 内核）
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

local function target_image(sprite, params)
    local layer = params.layer or 1
    local frame = params.frame or 1
    local image, err = _G._mcp_get_target_image(sprite, layer, frame)
    if not image then error(err) end
    return image
end

local function rgba(hex)
    local r, g, b = _mcp_hex_to_rgb(hex)
    return app.pixelColor.rgba(r, g, b, 255)
end

function _G._mcp_op_clear_canvas(sprite, params)
    local image = target_image(sprite, params)
    image:clear()
    return {cleared = true}
end

function _G._mcp_op_draw_pixel(sprite, params)
    local image = target_image(sprite, params)
    image:drawPixel(params.x, params.y, rgba(params.color))
    return {x = params.x, y = params.y}
end

function _G._mcp_op_draw_rect(sprite, params)
    local image = target_image(sprite, params)
    _mcp_rect(image, params.x, params.y, params.width, params.height,
              rgba(params.color), params.filled == true)
    return {x = params.x, y = params.y, width = params.width, height = params.height}
end

function _G._mcp_op_fill_region(sprite, params)
    local image = target_image(sprite, params)
    _mcp_fill(image, params.x, params.y, rgba(params.color), image.width, image.height)
    return {x = params.x, y = params.y}
end
```

实现要点：
- `_mcp_rect`、`_mcp_line`、`_mcp_ellipse` 直接复用 `scripts/mcp_common.lua:138-232` 中已有原语（此前是死代码）。
- `_mcp_op_fill_region` 用 `_mcp_fill`（`mcp_common.lua:206-223`），其参数为 target_color，不是源色，注意与旧 `fill_region.lua` 的语义核对。
- 边界：越界坐标由 `image:drawPixel` 原生处理，不额外校验。

- [ ] **Step 5: 不改 `mcp_common.lua`（裁定）**

`_mcp_get_or_create_sprite` 仍被 v1 的 `scripts/create_sprite.lua:31-32` 调用（`server.py:98` 仍注册旧工具，直到 Task 1.9）。v2 的 `_mcp_op_create_sprite` 本身始终新建、不复用活动 sprite，已满足 spec P0-7；旧 helper 随 v1 工具在 Task 1.9 退役后在阶段 3 一并删除。记录遗留缺陷：`mcp_common.lua:77` 的 `ColorMode.GRAYSCALE` 不是合法常量（应为 `ColorMode.GRAY`），仅影响 v1 灰度路径。

- [ ] **Step 6: 运行测试**

Run: `pytest tests/v2/test_lua_op_files.py -q`
Expected: PASS。

- [ ] **Step 7: 提交（若已授权）**

```bash
git add scripts/mcp_common.lua scripts/ops_session.lua scripts/ops_draw.lua tests/v2/test_lua_op_files.py
git commit -m "feat(v2): lua op libraries for session and drawing"
```

---

### Task 1.5: 执行器（锁、备份、undo/redo、编译执行）

**Files:**
- Create: `src/v2/executor.py`
- Test: `tests/v2/test_executor.py`

**Interfaces:**
- Consumes: `SessionManager`、runner（`run_script_path`）、`REGISTRY`、`compile_ops`、`parse_result_stdout`、`Envelope`
- Produces:
  - `Engine(session_manager, runner, config)`
  - `Engine.apply(session_id, raw_ops, *, atomic=True, dry_run=False) -> Envelope`
  - `Engine.undo(session_id) -> Envelope`、`Engine.redo(session_id) -> Envelope`
  - `BACKUP_NAME = "undo_backup.ase"`、`REDO_NAME = "redo_backup.ase"`

- [ ] **Step 1: 写失败测试**

```python
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.session import SessionManager
from src.v2.executor import Engine
from src.v2.result import ErrorCode


@pytest.fixture
def engine(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "cli"
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script_path.return_value = {
        "success": True,
        "stdout": '__MCP_JSON__{"ops":[{"op":"draw_pixel","ok":true,"data":{}}],"saved":true,"error":null}',
        "stderr": "",
    }
    return Engine(sm, runner, config), sm, runner


def _make_ase(sm, sid):
    path = sm.get_ase_path(sid)
    path.write_bytes(b"ASE")


def test_dry_run_does_not_run(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}], dry_run=True)
    assert env.ok is True
    assert env.changed is False
    runner.run_script_path.assert_not_called()


def test_apply_writes_batch_and_backs_up(engine):
    eng, sm, runner = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])
    assert env.ok is True
    assert env.changed is True
    work = sm.get_work_dir(sid)
    assert (work / "_batch.lua").exists()
    assert (work / "undo_backup.ase").exists()
    runner.run_script_path.assert_called_once()


def test_unknown_op_returns_invalid_args(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    env = eng.apply(sid, [{"op": "definitely_not_an_op"}])
    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS


def test_undo_redo_roundtrip(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    path = sm.get_ase_path(sid)
    path.write_bytes(b"BEFORE")
    shutil.copy2(path, path.parent / "undo_backup.ase")
    path.write_bytes(b"AFTER")

    assert eng.undo(sid).ok is True
    assert path.read_bytes() == b"BEFORE"
    assert eng.redo(sid).ok is True
    assert path.read_bytes() == b"AFTER"


def test_undo_without_backup_is_honest(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.undo(sid)
    assert env.ok is False
    assert env.error.code == ErrorCode.NO_MORE_UNDO


def test_redo_without_backup_is_honest(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)
    env = eng.redo(sid)
    assert env.ok is False
    assert env.error.code == ErrorCode.NO_MORE_REDO


def test_live_undo_redo_use_native_without_backups(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "ws"
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script.return_value = {"success": True, "stdout": "OK", "stderr": ""}
    eng = Engine(sm, runner, config)
    sid = sm.create_session(8, 8)
    _make_ase(sm, sid)

    assert eng.undo(sid).ok is True
    assert eng.redo(sid).ok is True
    assert runner.run_script.call_count == 2


def test_new_mutating_apply_clears_redo(engine):
    eng, sm, _ = engine
    sid = sm.create_session(8, 8)
    path = sm.get_ase_path(sid)
    path.write_bytes(b"V1")
    shutil.copy2(path, path.parent / "undo_backup.ase")
    path.write_bytes(b"V2")
    assert eng.undo(sid).ok is True          # 现在有 redo_backup
    assert (path.parent / "redo_backup.ase").exists()
    eng.apply(sid, [{"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}])
    assert not (path.parent / "redo_backup.ase").exists()


def test_undo_redo_unknown_session_returns_envelope(engine):
    eng, _, _ = engine
    env = eng.undo("missing")
    assert env.ok is False and env.error.code == ErrorCode.SESSION_NOT_FOUND
    env = eng.redo("missing")
    assert env.ok is False and env.error.code == ErrorCode.SESSION_NOT_FOUND
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_executor.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现**

```python
"""执行器：锁、备份、编译、单进程执行（spec §6）。"""

import contextlib
import shutil
import threading
import time
from pathlib import Path

from src.v2.compile import compile_ops, parse_result_stdout
from src.v2.registry import REGISTRY
from src.v2.result import Artifact, Envelope, ErrorCode, OpResult, UndoInfo

BACKUP_NAME = "undo_backup.ase"
REDO_NAME = "redo_backup.ase"


class Engine:
    def __init__(self, session_manager, runner, config):
        self.session_manager = session_manager
        self.runner = runner
        self.config = config
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    # ---------- public ----------

    @contextlib.contextmanager
    def session_lock(self, session_id: str):
        """公共每会话锁：run_lua 与 inspect 必须经此串行化。"""
        with self._lock(session_id):
            yield

    def apply(self, session_id, raw_ops, *, atomic=True, dry_run=False) -> Envelope:
        start = time.time()
        parsed, err = REGISTRY.validate(raw_ops)
        if err is not None:
            return Envelope.failure(
                err.code, err.message, hint=err.hint, op_index=err.op_index,
                session_id=session_id, mode=self.config.mode,
            )

        if dry_run:
            plan = [{"op": spec.name, "params": params.model_dump(mode="json")}
                    for spec, params in parsed]
            return Envelope(
                ok=True, session_id=session_id, mode=self.config.mode,
                op_results=[OpResult(op="plan", ok=True, data=plan)],
                changed=False,
                undo=UndoInfo(mode=self._undo_mode(), available=False),
                timing_ms=int((time.time() - start) * 1000),
            )

        with self._lock(session_id):
            return self._apply_locked(session_id, parsed, atomic, start)

    def undo(self, session_id) -> Envelope:
        with self._lock(session_id):
            try:
                work = self.session_manager.get_work_dir(session_id)
                path = self.session_manager.get_ase_path(session_id)
            except KeyError:
                return self._missing(session_id)
            if self.config.mode != "cli":
                return self._native("undo", session_id)
            backup = work / BACKUP_NAME
            if not backup.exists():
                return Envelope.failure(
                    ErrorCode.NO_MORE_UNDO, "nothing to undo (no backup)",
                    session_id=session_id, mode=self.config.mode,
                )
            if path.exists():
                shutil.copy2(path, work / REDO_NAME)
            shutil.copy2(backup, path)
            backup.unlink()
            return self._ok(session_id, "undo")

    def redo(self, session_id) -> Envelope:
        with self._lock(session_id):
            try:
                work = self.session_manager.get_work_dir(session_id)
                path = self.session_manager.get_ase_path(session_id)
            except KeyError:
                return self._missing(session_id)
            redo_backup = work / REDO_NAME
            if self.config.mode == "cli" and not redo_backup.exists():
                return Envelope.failure(
                    ErrorCode.NO_MORE_REDO, "nothing to redo",
                    session_id=session_id, mode=self.config.mode,
                )
            if self.config.mode == "cli":
                if path.exists():
                    shutil.copy2(path, work / BACKUP_NAME)
                shutil.copy2(redo_backup, path)
                redo_backup.unlink()
                return self._ok(session_id, "redo")
            return self._native("redo", session_id)

    # ---------- internals ----------

    def _missing(self, session_id) -> Envelope:
        return Envelope.failure(
            ErrorCode.SESSION_NOT_FOUND, f"session not found: {session_id}",
            session_id=session_id, mode=self.config.mode,
        )

    def _undo_mode(self) -> str:
        return "file_backup" if self.config.mode == "cli" else "transaction"

    def _ok(self, session_id, action: str) -> Envelope:
        return Envelope(
            ok=True, session_id=session_id, mode=self.config.mode,
            op_results=[OpResult(op=action, ok=True)],
            changed=True,
            undo=UndoInfo(mode=self._undo_mode(), available=True),
        )

    def _native(self, action: str, session_id) -> Envelope:
        result = self.runner.run_script(f"{action}.lua", {
            "file": str(self.session_manager.get_ase_path(session_id)),
        })
        if not result["success"]:
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR,
                result.get("error", f"{action} failed"),
                session_id=session_id, mode=self.config.mode,
            )
        return self._ok(session_id, action)

    def _apply_locked(self, session_id, parsed, atomic, start) -> Envelope:
        session = self.session_manager
        try:
            work = session.get_work_dir(session_id)
            path = session.get_ase_path(session_id)
        except KeyError:
            return Envelope.failure(
                ErrorCode.SESSION_NOT_FOUND, f"session not found: {session_id}",
                session_id=session_id, mode=self.config.mode,
            )

        mutating = any(spec.mutating for spec, _ in parsed)
        if mutating and self.config.mode == "cli":
            # 新编辑清空 redo 栈（标准 undo 语义）
            (work / REDO_NAME).unlink(missing_ok=True)
            if path.exists():
                shutil.copy2(path, work / BACKUP_NAME)

        source = compile_ops(
            [(s, p) for s, p in parsed if s.lua],
            file_path=path,
            scripts_dir=self.config.scripts_dir,
            atomic=atomic,
        )
        batch = work / "_batch.lua"
        batch.write_text(source, encoding="utf-8")

        result = self.runner.run_script_path(str(batch), {})
        if not result["success"]:
            return Envelope.failure(
                ErrorCode.SCRIPT_ERROR,
                result.get("error", "aseprite script failed"),
                hint=result.get("stderr", ""),
                session_id=session_id, mode=self.config.mode,
            )
        try:
            payload = parse_result_stdout(result.get("stdout", ""))
        except ValueError as exc:
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR, str(exc),
                session_id=session_id, mode=self.config.mode,
            )

        op_results = [
            OpResult(op=r.get("op", "?"), ok=bool(r.get("ok")), data=r.get("data"))
            for r in payload.get("ops", [])
        ]
        failed = next((i for i, r in enumerate(op_results) if not r.ok), None)
        if failed is not None or payload.get("error"):
            return Envelope.failure(
                ErrorCode.OP_FAILED,
                str(payload.get("error") or "op failed"),
                op_index=failed,
                session_id=session_id, mode=self.config.mode,
                op_results=op_results,
            )

        artifacts = self._collect_artifacts(payload)
        return Envelope(
            ok=True, session_id=session_id, mode=self.config.mode,
            op_results=op_results,
            artifacts=artifacts,
            changed=bool(mutating and payload.get("saved")),
            undo=UndoInfo(mode=self._undo_mode(), available=mutating),
            timing_ms=int((time.time() - start) * 1000),
        )

    def _collect_artifacts(self, payload: dict) -> list[Artifact]:
        out: list[Artifact] = []
        for r in payload.get("ops", []):
            data = r.get("data") or {}
            if isinstance(data, dict) and data.get("artifact_path"):
                out.append(Artifact(
                    kind=data.get("artifact_kind", "png"),
                    path=data["artifact_path"],
                    role=data.get("artifact_role", r.get("op", "output")),
                ))
        return out
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/v2/test_executor.py -q`
Expected: PASS。

- [ ] **Step 5: 提交（若已授权）**

```bash
git add src/v2/executor.py tests/v2/test_executor.py
git commit -m "feat(v2): engine with locking, backups and undo/redo"
```

---

### Task 1.6: session 与 draw 的 Python op 定义

**Files:**
- Create: `src/v2/ops/__init__.py`（汇总并触发注册）
- Create: `src/v2/ops/session_ops.py`
- Create: `src/v2/ops/draw_ops.py`
- Test: `tests/v2/test_op_definitions.py`

**Interfaces:**
- Consumes: `REGISTRY`、`OpSpec`
- Produces: 已注册 op：`create_sprite`、`open_sprite`、`save_sprite`、`close_session`（session）；`clear_canvas`、`draw_pixel`、`draw_rect`、`fill_region`（draw）。所有 mutating draw op 默认 `layer=1, frame=1`。

- [ ] **Step 1: 写失败测试**

```python
from src.v2.ops import REGISTRY  # noqa: F401  触发注册
from src.v2.registry import REGISTRY as R


def test_expected_ops_registered():
    names = set(R.names())
    assert {"create_sprite", "open_sprite", "save_sprite", "close_session",
            "clear_canvas", "draw_pixel", "draw_rect", "fill_region"} <= names


def test_draw_defaults():
    spec = R.get("draw_pixel")
    params = spec.params.model_validate({"x": 1, "y": 2, "color": "#FF0000"})
    assert params.layer == 1 and params.frame == 1
    assert spec.mutating is True


def test_create_sprite_requires_size():
    spec = R.get("create_sprite")
    params = spec.params.model_validate({"width": 16, "height": 16})
    assert params.color_mode == "rgb"


def test_close_session_is_destructive():
    assert R.get("close_session").destructive is True
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_op_definitions.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现 `src/v2/ops/session_ops.py`**

```python
"""会话生命周期 op（spec §5）。"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.v2.registry import OpSpec, REGISTRY


class ColorMode(str, Enum):
    rgb = "rgb"
    grayscale = "grayscale"
    indexed = "indexed"


class CreateSprite(BaseModel):
    width: int = Field(ge=1, le=4096)
    height: int = Field(ge=1, le=4096)
    color_mode: ColorMode = ColorMode.rgb
    file: Optional[str] = None


class OpenSprite(BaseModel):
    path: str
    file: Optional[str] = None


class SaveSprite(BaseModel):
    path: Optional[str] = None


class CloseSession(BaseModel):
    pass


def register() -> None:
    REGISTRY.register(OpSpec("create_sprite", "session", CreateSprite,
                             lua="_mcp_op_create_sprite", mutating=True))
    REGISTRY.register(OpSpec("open_sprite", "session", OpenSprite,
                             lua="_mcp_op_open_sprite", mutating=True))
    REGISTRY.register(OpSpec("save_sprite", "session", SaveSprite,
                             lua="_mcp_op_save_sprite", mutating=True))
    REGISTRY.register(OpSpec("close_session", "session", CloseSession,
                             mutating=True, destructive=True))
```

说明：`file` 字段由执行器注入为会话 `.ase` 路径；`close_session` 不生成 Lua，由工具层在执行后清理 session。

- [ ] **Step 4: 实现 `src/v2/ops/draw_ops.py`**

```python
"""绘制 op 定义（第一批）。"""

from typing import Optional

from pydantic import BaseModel, Field

from src.v2.registry import OpSpec, REGISTRY

_HEX = r"^#[0-9A-Fa-f]{6}$"


class _Targeted(BaseModel):
    layer: int = Field(default=1, ge=1)
    frame: int = Field(default=1, ge=1)


class ClearCanvas(_Targeted):
    pass


class DrawPixel(_Targeted):
    x: int
    y: int
    color: str = Field(pattern=_HEX)


class DrawRect(_Targeted):
    x: int
    y: int
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    color: str = Field(pattern=_HEX)
    filled: bool = False


class FillRegion(_Targeted):
    x: int
    y: int
    color: str = Field(pattern=_HEX)


def register() -> None:
    REGISTRY.register(OpSpec("clear_canvas", "draw", ClearCanvas,
                             lua="_mcp_op_clear_canvas", mutating=True, destructive=True))
    REGISTRY.register(OpSpec("draw_pixel", "draw", DrawPixel,
                             lua="_mcp_op_draw_pixel", mutating=True))
    REGISTRY.register(OpSpec("draw_rect", "draw", DrawRect,
                             lua="_mcp_op_draw_rect", mutating=True))
    REGISTRY.register(OpSpec("fill_region", "draw", FillRegion,
                             lua="_mcp_op_fill_region", mutating=True))


register()
```

- [ ] **Step 5: 实现 `src/v2/ops/__init__.py`**

```python
"""导入即注册所有内置 op。"""

from src.v2.ops import draw_ops, session_ops  # noqa: F401

from src.v2.registry import REGISTRY  # re-export

__all__ = ["REGISTRY"]
```

- [ ] **Step 6: 运行测试**

Run: `pytest tests/v2/test_op_definitions.py -q`
Expected: PASS。

- [ ] **Step 7: 提交（若已授权）**

```bash
git add src/v2/ops tests/v2/test_op_definitions.py
git commit -m "feat(v2): python op definitions for session and draw"
```

---

### Task 1.7: `apply_operations` 工具

**Files:**
- Create: `src/v2/tools.py`
- Create: `tests/v2/conftest.py`（共享 fixture）
- Test: `tests/v2/test_apply_tool.py`

**Interfaces:**
- Consumes: `Engine`、`REGISTRY`、`Envelope`
- Produces: `register_v2_tools(mcp, session_manager, runner, config)`；注册 `apply_operations`、`run_lua`、`inspect`（`inspect` 在 Task 2.2 实现，此前用占位函数并在该任务替换）。

- [ ] **Step 1: 写共享 fixture 与失败测试**

`tests/v2/conftest.py`：

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.session import SessionManager
from src.v2.tools import register_v2_tools


@pytest.fixture
def tools(tmp_path):
    config = Config()
    config.work_dir = tmp_path
    config.mode = "cli"
    sm = SessionManager(config)
    runner = MagicMock()
    runner.run_script_path.return_value = {
        "success": True,
        "stdout": '__MCP_JSON__{"ops":[{"op":"draw_pixel","ok":true,"data":{}}],"saved":true,"error":null}',
        "stderr": "",
    }
    captured = {}
    mcp = MagicMock()

    def capture(func=None, **kwargs):
        if func is None:
            return lambda f: capture(f, **kwargs)
        captured[func.__name__] = func
        return func

    mcp.tool = capture
    register_v2_tools(mcp, sm, runner, config)
    return captured, sm, runner
```

`tests/v2/test_apply_tool.py`（不再定义 fixture，直接使用 conftest 的 `tools`）：

```python
from src.v2.result import ErrorCode


def test_apply_operations_happy_path(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    env = captured["apply_operations"](session_id=sid, ops=[
        {"op": "draw_pixel", "x": 1, "y": 1, "color": "#FF0000"}
    ])
    assert env.ok is True
    assert env.changed is True
    assert runner.run_script_path.called


def test_apply_operations_unknown_op(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    env = captured["apply_operations"](session_id=sid, ops=[{"op": "nope"}])
    assert env.ok is False
    assert env.error.code == ErrorCode.INVALID_ARGS


def test_apply_operations_missing_session(tools):
    captured, _, _ = tools
    env = captured["apply_operations"](session_id="missing", ops=[
        {"op": "draw_pixel", "x": 0, "y": 0, "color": "#000000"}
    ])
    assert env.ok is False
    assert env.error.code == ErrorCode.SESSION_NOT_FOUND


def test_apply_operations_session_created_by_first_op(tools):
    captured, sm, _ = tools
    env = captured["apply_operations"](ops=[
        {"op": "create_sprite", "width": 8, "height": 8}
    ])
    assert env.ok is True
    assert env.session_id in [s["session_id"] for s in sm.list_sessions()]


def test_dry_run_does_not_create_session(tools):
    captured, sm, _ = tools
    before = len(sm.list_sessions())
    env = captured["apply_operations"](
        ops=[{"op": "create_sprite", "width": 8, "height": 8}], dry_run=True
    )
    assert env.ok is True
    assert len(sm.list_sessions()) == before


def test_dry_run_does_not_close_session(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    env = captured["apply_operations"](
        session_id=sid, ops=[{"op": "close_session"}], confirmed=True, dry_run=True
    )
    assert env.ok is True
    assert sid in [s["session_id"] for s in sm.list_sessions()]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_apply_tool.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现 `apply_operations` 与 `run_lua`**

```python
"""v2 工具面（spec §5）。"""

from typing import Optional

from fastmcp.utilities.types import Image  # noqa: F401  (inspect 在 Task 2.2 使用)

from src.v2.executor import Engine
from src.v2.registry import REGISTRY
from src.v2.result import Envelope, ErrorCode, OpResult


def register_v2_tools(mcp, session_manager, runner, config):
    engine = Engine(session_manager, runner, config)

    @mcp.tool(annotations={"destructiveHint": True, "openWorldHint": False})
    def apply_operations(
        ops: list[dict],
        session_id: Optional[str] = None,
        atomic: bool = True,
        dry_run: bool = False,
        confirmed: bool = False,
    ) -> Envelope:
        """执行一批 Aseprite 操作（唯一变更入口）。

        如果 session_id 为空且首个 op 是 create_sprite/open_sprite，
        会先创建会话再执行。destructive op 需要 confirmed=true。
        """
        if not ops:
            return Envelope.failure(
                ErrorCode.INVALID_ARGS, "ops must be a non-empty list",
                session_id=session_id, mode=config.mode,
            )

        # 先校验再建 session：参数不合法时不泄漏工作目录
        parsed, err = REGISTRY.validate(ops)
        if err is not None:
            return Envelope.failure(
                err.code, err.message, hint=err.hint, op_index=err.op_index,
                session_id=session_id, mode=config.mode,
            )

        # 确认门在建 session 之前：被拒的批量不得产生副作用
        if not confirmed and any(spec.destructive for spec, _ in parsed):
            return Envelope.failure(
                ErrorCode.CONFIRMATION_REQUIRED,
                "batch contains destructive ops",
                hint="re-call with confirmed=true",
                session_id=session_id, mode=config.mode,
            )

        first = ops[0].get("op") if isinstance(ops[0], dict) else None
        if session_id is None and first in ("create_sprite", "open_sprite") and not dry_run:
            session_id = session_manager.create_session(
                width=int(ops[0].get("width", 1)),
                height=int(ops[0].get("height", 1)),
                color_mode=str(ops[0].get("color_mode", "rgb")),
            )
            ops = [dict(o) for o in ops]
            ops[0]["file"] = str(session_manager.get_ase_path(session_id))

        env = engine.apply(session_id, ops, atomic=atomic, dry_run=dry_run)

        if env.ok and not dry_run and any(spec.name == "close_session" for spec, _ in parsed):
            if session_id:
                session_manager.close_session(session_id)
        return env

    @mcp.tool(annotations={"destructiveHint": True, "openWorldHint": False})
    def run_lua(session_id: str, code: str, unsafe: bool = False, confirmed: bool = False) -> Envelope:
        """执行任意 Lua（逃逸舱）。必须 unsafe=true 且 confirmed=true。"""
        if not unsafe:
            return Envelope.failure(
                ErrorCode.UNSUPPORTED_IN_MODE,
                "run_lua requires unsafe=true",
                hint="prefer apply_operations; run_lua can break documents",
                session_id=session_id, mode=config.mode,
            )
        if not confirmed:
            return Envelope.failure(
                ErrorCode.CONFIRMATION_REQUIRED,
                "run_lua requires confirmed=true",
                hint="re-call with confirmed=true",
                session_id=session_id, mode=config.mode,
            )
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/v2/test_apply_tool.py -q`
Expected: PASS。

- [ ] **Step 5: 提交（若已授权）**

```bash
git add src/v2/tools.py tests/v2/test_apply_tool.py
git commit -m "feat(v2): apply_operations tool"
```

---

### Task 1.8: `run_lua` 工具

**Files:**
- Modify: `src/v2/tools.py`（替换 `NotImplementedError` 分支）
- Create: `scripts/mcp_run_lua.lua`
- Test: `tests/v2/test_run_lua_tool.py`

**Interfaces:**
- Consumes: `run_script_with_file` 风格参数（`file`、`code`）
- Produces: `run_lua` 返回 `Envelope`，`op_results=[OpResult(op="run_lua", data={"stdout": str})]`。

- [ ] **Step 1: 写失败测试**

```python
def test_run_lua_requires_unsafe(tools):
    captured, sm, _ = tools
    sid = sm.create_session(8, 8)
    env = captured["run_lua"](session_id=sid, code="print(1)")
    assert env.ok is False
    assert env.error.code.value == "unsupported_in_mode"


def test_run_lua_executes_when_unsafe(tools):
    captured, sm, runner = tools
    sid = sm.create_session(8, 8)
    sm.get_ase_path(sid).write_bytes(b"ASE")
    runner.run_script.return_value = {"success": True, "stdout": "1\n", "stderr": ""}
    env = captured["run_lua"](session_id=sid, code="print(1)", unsafe=True)
    assert env.ok is True
    assert env.op_results[0].data["stdout"].strip() == "1"
```

（`tools` fixture 已在 Task 1.7 放入 `tests/v2/conftest.py`，此处直接使用。）

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_run_lua_tool.py -q`
Expected: FAIL（`NotImplementedError`）。

- [ ] **Step 3: 实现 Lua 脚本**

`scripts/mcp_run_lua.lua`：

```lua
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

local file = app.params["file"]
local code = app.params["code"] or ""
local sprite = _G._mcp_get_sprite(file)
if not sprite then
    error("no sprite. Call create_sprite first.")
end

-- code 以 params 传入的是 key=value 字符串；v2 改用文件旁路：
-- Python 写 <work>/_run_lua.lua 并把路径放入 code 参数
if app.params["code_path"] and app.params["code_path"] ~= "" then
    dofile(app.params["code_path"])
else
    error("code_path is required")
end
_G._mcp_maybe_save(sprite, file)
```

- [ ] **Step 4: 实现 Python 分支**

替换 `run_lua` 的 `raise NotImplementedError(...)`：

```python
        try:
            work = session_manager.get_work_dir(session_id)
        except KeyError:
            return Envelope.failure(
                ErrorCode.SESSION_NOT_FOUND, f"session not found: {session_id}",
                session_id=session_id, mode=config.mode,
            )
        snippet = work / "_run_lua.lua"
        with engine.session_lock(session_id):
            snippet.write_text(code, encoding="utf-8")
            result = runner.run_script("mcp_run_lua.lua", {
                "file": str(session_manager.get_ase_path(session_id)),
                "code_path": str(snippet),
            })
        if not result["success"]:
            return Envelope.failure(
                ErrorCode.LUA_RUNTIME_ERROR,
                result.get("error", "run_lua failed"),
                hint=result.get("stderr", ""),
                session_id=session_id, mode=config.mode,
            )
        return Envelope(
            ok=True, session_id=session_id, mode=config.mode,
            op_results=[OpResult(op="run_lua", ok=True,
                                 data={"stdout": result.get("stdout", "")})],
            changed=True,
        )

    return engine
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/v2/test_run_lua_tool.py tests/v2/test_apply_tool.py -q`
Expected: PASS。

- [ ] **Step 6: 提交（若已授权）**

```bash
git add src/v2/tools.py scripts/mcp_run_lua.lua tests/v2/
git commit -m "feat(v2): run_lua escape hatch"
```

---

### Task 1.9: v2 接入 server 并退役旧工具注册

**Files:**
- Modify: `server.py:22-39,98-114`
- Modify: `tests/test_server.py`
- Modify: `src/v2/tools.py`（`inspect` 占位注册）

**Interfaces:**
- Consumes: `register_v2_tools`
- Produces: `create_server()` 只注册 3 个工具 + 资源 + 提示；旧 `register_*_tools` 不再调用（模块与测试暂时保留，阶段 3 清理）。

- [ ] **Step 1: 修改 server 注册**

删除 `server.py:22-37` 的 16 行 `register_xxx_tools` 导入与 `98-114` 的调用，替换为：

```python
from src.v2.tools import register_v2_tools
...
    register_v2_tools(mcp, session_manager, runner, config)
```

保留 `register_resources` / `register_prompts`（`server.py:117,120`）。

同时修 P0-8：`server.py:57-63` 的 WS 启动失败回退分支中，把 `config.mode` 同步改为 `"cli"`：

```python
            runner = AsepriteRunner(config)
            config.mode = "cli"  # 与 runner 保持一致（spec P0-8）
```

`src/v2/tools.py` 末尾追加占位（Task 2.2 替换）：

```python
    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def inspect(session_id: str, scale: int = 4) -> Image:
        """感知画布（占位，Task 2.2 实现）。"""
        raise NotImplementedError("inspect implemented in Task 2.2")
```

- [ ] **Step 2: 更新 server 测试**

`tests/test_server.py` 中断言工具数量的用例改为断言 3 个工具名：

```python
EXPECTED_TOOLS = {"apply_operations", "inspect", "run_lua"}
```

若原测试只验证 `create_server()` 可构造，则追加：

```python
def test_v2_tools_registered():
    import asyncio
    from server import create_server

    mcp = create_server()
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == {"apply_operations", "inspect", "run_lua"}
```

- [ ] **Step 3: 运行 server 与全量测试**

Run: `pytest tests/test_server.py -q` → PASS
Run: `pytest -m "not e2e" -q` → 预期：v2 测试通过；**旧工具模块测试仍通过**（它们直接测模块，不经 server）。凡因 server 不再注册而失败的用例，改为直接测模块或标记 `pytest.mark.skip(reason="retired in v2")` 并记录在计划附录。

- [ ] **Step 4: 手动冒烟**

Run:
```bash
python -c "from server import create_server; import asyncio; m=create_server(); print(sorted(t.name for t in asyncio.run(m.list_tools())))"
```
Expected: `['apply_operations', 'inspect', 'run_lua']`。

- [ ] **Step 5: 提交（若已授权）**

```bash
git add server.py tests/test_server.py src/v2/tools.py
git commit -m "feat(v2): wire 3-tool server"
```

---

### Task 2.1: 安全的 inspect Lua 导出（修 P0-1）

**Files:**
- Create: `scripts/inspect.lua`
- Test: `tests/v2/test_inspect_script.py`

**Interfaces:**
- Consumes: `app.params`: `file`、`output`、`scale`、`view`、`layers`、`frames`
- Produces: JSON 到 stdout：`{"width","height","frames","layers":[...],"palette":[...],"tags":[...]}`；PNG 写 `output`。**绝不修改源文档。**

- [ ] **Step 1: 写回归测试（关键）**

```python
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def test_inspect_never_resizes_source():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    # 缩放只能发生在临时副本上
    assert "Sprite(sprite)" in text or "Sprite(_sprite)" in text
    assert "sprite:resize" not in text
    assert "_mcp_get_sprite" in text
    assert "saveCopyAs" in text


def test_inspect_prints_json_marker():
    text = (SCRIPTS / "inspect.lua").read_text(encoding="utf-8")
    assert "json.encode" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_inspect_script.py -q`
Expected: FAIL，文件不存在。

- [ ] **Step 3: 实现 `scripts/inspect.lua`**

```lua
-- inspect.lua：只读感知。永远在临时副本上缩放/导出（修 P0-1）。
if not _G._mcp_common_loaded then
    local d = debug.getinfo(1, "S").source:match("@(.*[/\\])")
    if d then pcall(dofile, d .. "mcp_common.lua") end
end

local file = app.params["file"]
local output = app.params["output"]
local scale = tonumber(app.params["scale"] or "4")
local view = app.params["view"] or "composite"

if not output then error("output is required") end

local sprite = _G._mcp_get_sprite(file)
if not sprite then error("no sprite. Call create_sprite first.") end

local layers = {}
for i, layer in ipairs(sprite.layers) do
    layers[i] = {name = layer.name, visible = layer.isVisible, opacity = layer.opacity}
end
local frames = {}
for i, frame in ipairs(sprite.frames) do
    frames[i] = {number = i, duration = frame.duration}
end
local palette = {}
for i = 0, #sprite.palettes[1] - 1 do
    local c = sprite.palettes[1]:getColor(i)
    palette[i + 1] = string.format("#%02X%02X%02X", c.red, c.green, c.blue)
end
local tags = {}
for i, tag in ipairs(sprite.tags) do
    tags[i] = {name = tag.name, from = tag.fromFrame.frameNumber, to = tag.toFrame.frameNumber}
end

-- 临时副本：缩放与导出都不触碰原文档
local preview = Sprite(sprite)
if scale > 1 then
    preview:resize(preview.width * scale, preview.height * scale)
end
preview:saveCopyAs(output)
preview:close()

print(json.encode({
    width = sprite.width, height = sprite.height,
    frames = frames, layers = layers, palette = palette, tags = tags, view = view,
}))
```

若 `view == "silhouette"`：在副本上把非透明像素染黑后再导出（复用 `export_silhouette.lua:30-55` 的循环思路），其余视图暂等同 composite。

- [ ] **Step 4: 运行测试**

Run: `pytest tests/v2/test_inspect_script.py -q`
Expected: PASS。

- [ ] **Step 5: 提交（若已授权）**

```bash
git add scripts/inspect.lua tests/v2/test_inspect_script.py
git commit -m "fix(v2): safe inspect export on temp copy (P0-1)"
```

---

### Task 2.2: `inspect` 工具与量化指标

**Files:**
- Create: `src/v2/inspect.py`
- Modify: `src/v2/tools.py`（替换占位 `inspect`）
- Create: `tests/v2/test_inspect_tool.py`

**Interfaces:**
- Consumes: `scripts/inspect.lua`、PIL、`Engine` 的会话路径
- Produces:
  - `compute_metrics(png_path: Path, meta: dict) -> dict`，键：`color_count`、`palette`、`near_duplicate_colors`、`bbox`、`coverage`、`semi_transparent_pixels`、`isolated_pixels`、`grid_offset`、`frame_diffs`
  - `inspect` 返回 `fastmcp.tools.ToolResult`：`content=[Image]` + `structured_content={"meta":…, "metrics":…}`（Task 0.2 已验证该 API 可用，见 `tests/v2/test_fastmcp_capabilities.py:32-42`），同时写 `work/<sid>/metrics.json`。

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

from PIL import Image as PILImage

from src.v2.inspect import compute_metrics


def _png(tmp_path: Path) -> Path:
    img = PILImage.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(4):
        img.putpixel((x, 0), (255, 0, 0, 255))
    img.putpixel((7, 7), (0, 255, 0, 128))
    p = tmp_path / "p.png"
    img.save(p)
    return p


def test_compute_metrics(tmp_path):
    m = compute_metrics(_png(tmp_path), {"width": 8, "height": 8, "frames": [], "layers": []})
    assert m["color_count"] == 2
    assert m["semi_transparent_pixels"] == 1
    assert m["coverage"] == 5 / 64
    assert m["bbox"] == {"x": 0, "y": 0, "width": 8, "height": 8}


def test_near_duplicate_detection(tmp_path):
    img = PILImage.new("RGBA", (4, 4), (0, 0, 0, 0))
    img.putpixel((0, 0), (100, 100, 100, 255))
    img.putpixel((1, 0), (102, 100, 100, 255))
    p = tmp_path / "q.png"
    img.save(p)
    m = compute_metrics(p, {"width": 4, "height": 4, "frames": [], "layers": []})
    assert m["near_duplicate_colors"]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/v2/test_inspect_tool.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现 `src/v2/inspect.py`**

```python
"""感知指标：从导出的 PNG + Lua 元数据计算（spec §8）。"""

from collections import Counter
from pathlib import Path

from PIL import Image


def _bbox(pixels, width, height):
    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > 0:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return {"x": min(xs), "y": min(ys),
            "width": max(xs) - min(xs) + 1, "height": max(ys) - min(ys) + 1}


def _isolated(pixels, width, height) -> int:
    count = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] == 0:
                continue
            neighbors = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and pixels[nx, ny][3] > 0:
                    neighbors += 1
            if neighbors == 0:
                count += 1
    return count


def _near_duplicates(colors: list[tuple[int, ...]], threshold: int = 8) -> list[list[str]]:
    dupes = []
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            a, b = colors[i], colors[j]
            if all(abs(a[k] - b[k]) <= threshold for k in range(3)):
                if a[3] == b[3]:
                    dupes.append(["#%02X%02X%02X" % a[:3], "#%02X%02X%02X" % b[:3]])
    return dupes


def compute_metrics(png_path: Path, meta: dict) -> dict:
    img = Image.open(png_path).convert("RGBA")
    width, height = img.size
    pixels = img.load()
    histogram = Counter(pixels[x, y] for y in range(height) for x in range(width))
    opaque = {c: n for c, n in histogram.items() if c[3] > 0}
    colors = list(opaque)
    semi = sum(n for c, n in histogram.items() if 0 < c[3] < 255)
    opaque_count = sum(n for c, n in opaque.items())
    return {
        "width": width,
        "height": height,
        "color_count": len(opaque),
        "palette": ["#%02X%02X%02X" % c[:3] for c in colors],
        "near_duplicate_colors": _near_duplicates(colors),
        "bbox": _bbox(pixels, width, height),
        "coverage": opaque_count / (width * height),
        "semi_transparent_pixels": semi,
        "isolated_pixels": _isolated(pixels, width, height),
        "grid_offset": {"x": 0, "y": 0},
        "frame_diffs": [],
    }
```

`grid_offset` 与 `frame_diffs` 在本任务返回保守默认值；多帧 diff 在阶段 3 用 `compare_frames.lua` 补齐（记录为已知限制）。

- [ ] **Step 4: 实现 `inspect` 工具**

替换 `src/v2/tools.py` 的占位：

```python
    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def inspect(session_id: str, scale: int = 4, view: str = "composite") -> ToolResult:
        """返回画布预览与量化指标（只读，永不改动文档）。"""
        from fastmcp.tools import ToolResult

        from src.v2.inspect import compute_metrics

        try:
            work = session_manager.get_work_dir(session_id)
            ase = session_manager.get_ase_path(session_id)
        except KeyError:
            raise ValueError(f"session not found: {session_id}")

        png = work / "preview.png"
        result = runner.run_script("inspect.lua", {
            "file": str(ase), "output": str(png),
            "scale": str(scale), "view": view,
        })
        if not result["success"]:
            raise RuntimeError(result.get("error", "inspect failed"))

        import json

        meta = json.loads(result["stdout"].strip().splitlines()[-1])
        metrics = compute_metrics(png, meta)
        (work / "metrics.json").write_text(
            json.dumps({"meta": meta, "metrics": metrics}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ToolResult(
            content=[Image(path=str(png))],
            structured_content={"meta": meta, "metrics": metrics},
        )
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/v2/test_inspect_tool.py -q`
Expected: PASS。

- [ ] **Step 6: 全量回归**

Run: `pytest -m "not e2e" -q`
Expected: 全绿（或因 Task 1.9 已记录的退役用例跳过）。

- [ ] **Step 7: 提交（若已授权）**

```bash
git add src/v2/inspect.py src/v2/tools.py tests/v2/test_inspect_tool.py
git commit -m "feat(v2): inspect tool with quantitative metrics"
```

---

### Task 2.3: 文档同步（AGENTS.md / README 工具面）

**Files:**
- Modify: `AGENTS.md`（架构与命令段）
- Modify: `README.md` / `README_CN.md`（工具目录：3 工具 + op 目录说明）

**Interfaces:**
- Consumes: 已实现的 v2
- Produces: 文档与代码一致；`AGENTS.md` 的"Adding a feature"改为"添加 op"流程。

- [ ] **Step 1: 更新 AGENTS.md 架构段**

把工具面描述改为：

```
src/v2/              注册表、编译、执行器、结果信封、inspect
src/v2/ops/          内置 op 定义（Pydantic 参数模型）
scripts/ops_*.lua    op 的 Lua 实现，按 category 组织
scripts/inspect.lua  只读感知导出（临时副本，永不改文档）
```

并把"Adding a feature"改为：① 在 `scripts/ops_<category>.lua` 写 `_mcp_op_<name>`；② 在 `src/v2/ops/<category>_ops.py` 定义 Pydantic 参数并 `REGISTRY.register`；③ 补 `tests/v2/` 用例。

- [ ] **Step 2: 更新 README 工具表**

用 3 工具 + "op 目录见 `aseprite://ops`" 替换旧 75 工具表；保留 Live 模式配置与示例工作流。

- [ ] **Step 3: 检查链接与命令可执行**

Run: `pytest -m "not e2e" -q`
Expected: PASS。

- [ ] **Step 4: 提交（若已授权）**

```bash
git add AGENTS.md README.md README_CN.md
git commit -m "docs: document v2 three-tool surface"
```

---

## 附录 A：本计划已知限制（阶段 3 解决）

- `grid_offset`、`frame_diffs` 为占位值，待 `compare_frames.lua` 迁移后补齐。
- 除 `draw_pixel/draw_rect/fill_region/clear_canvas` 外，其余旧工具未迁移；旧模块保留但不在 server 注册，阶段 3 批量迁移后删除。
- guard-pattern elicitation 未接入，`confirmation_required` 采用显式 `confirmed` 重新调用（跨客户端一致，无协议依赖）。
- CLI 批量中途失败时 `op_results` 可能不完整（事务回滚后 Lua 提前 `error`），阶段 3 改为在事务内收集完整失败列表。
- P0-5 的根因（选区随进程丢失）由事务内核结构性消除；选区类 op（select/delete_selection）在阶段 3 迁移，届时补跨 op 选区保持的测试。
- P0-6 的根因（Python 侧尺寸缓存漂移）随旧 `get_canvas_info` 退役消除；画布元数据改由 `inspect` 每次从 Lua 读取。

## 附录 B：退役用例记录

Task 1.9 执行时，在此逐条记录被 `pytest.mark.skip(reason="retired in v2")` 的旧测试：`文件::用例 → 原因 → 计划迁移阶段`。

- `tests/test_server.py::test_create_server_registers_tileset_and_quality_tools` → server 不再导入/调用 `register_tileset_tools`/`register_quality_tools`（旧工具注册退役）→ 阶段 3 随旧工具模块一并删除（该用例测的是已退役的 server 注册行为，无迁移价值）。
