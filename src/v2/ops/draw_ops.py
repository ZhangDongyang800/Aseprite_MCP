"""Drawing op definitions (first batch)."""

from pydantic import BaseModel, ConfigDict, Field

from src.v2.registry import OpSpec, REGISTRY

_HEX = r"^#[0-9A-Fa-f]{6}$"


class _Targeted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: int = Field(default=1, ge=1)
    frame: int = Field(default=1, ge=1)


class ClearCanvas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # layer=0 is a frame-wide clear across every layer; 1-based otherwise.
    layer: int = Field(default=1, ge=0)
    frame: int = Field(default=1, ge=1)


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


class DrawLine(_Targeted):
    x1: int
    y1: int
    x2: int
    y2: int
    color: str = Field(pattern=_HEX)


class DrawEllipse(_Targeted):
    cx: int
    cy: int
    rx: int = Field(ge=1)
    ry: int = Field(ge=1)
    color: str = Field(pattern=_HEX)
    filled: bool = False


class PaintGrid(_Targeted):
    path: str
    x: int = Field(default=0, ge=0)
    y: int = Field(default=0, ge=0)


def register() -> None:
    REGISTRY.register(OpSpec("clear_canvas", "draw", ClearCanvas,
                             lua="_mcp_op_clear_canvas", mutating=True, destructive=True))
    REGISTRY.register(OpSpec("draw_pixel", "draw", DrawPixel,
                             lua="_mcp_op_draw_pixel", mutating=True))
    REGISTRY.register(OpSpec("draw_rect", "draw", DrawRect,
                             lua="_mcp_op_draw_rect", mutating=True))
    REGISTRY.register(OpSpec("fill_region", "draw", FillRegion,
                             lua="_mcp_op_fill_region", mutating=True))
    REGISTRY.register(OpSpec("draw_line", "draw", DrawLine,
                             lua="_mcp_op_draw_line", mutating=True))
    REGISTRY.register(OpSpec("draw_ellipse", "draw", DrawEllipse,
                             lua="_mcp_op_draw_ellipse", mutating=True))
    REGISTRY.register(OpSpec("paint_grid", "draw", PaintGrid,
                             lua="_mcp_op_paint_grid", mutating=True))


register()
