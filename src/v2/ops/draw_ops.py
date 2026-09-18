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
