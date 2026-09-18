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
