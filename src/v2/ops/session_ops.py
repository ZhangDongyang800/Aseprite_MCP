"""Session lifecycle ops (spec §5)."""

from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.v2.registry import OpSpec, REGISTRY

HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class ColorMode(str, Enum):
    rgb = "rgb"
    grayscale = "grayscale"
    indexed = "indexed"


class CreateSprite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(ge=1, le=4096)
    height: int = Field(ge=1, le=4096)
    color_mode: ColorMode = ColorMode.rgb
    file: Optional[str] = None


class OpenSprite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    file: Optional[str] = None


class SaveSprite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Optional[str] = None


class CloseSession(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Layer", min_length=1, max_length=64)
    opacity: int = Field(default=255, ge=0, le=255)


class SetLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: int = Field(ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    opacity: Optional[int] = Field(default=None, ge=0, le=255)
    visible: Optional[bool] = None

    @model_validator(mode="after")
    def _needs_a_change(self):
        if self.name is None and self.opacity is None and self.visible is None:
            raise ValueError("set_layer needs name, opacity or visible")
        return self


class DeleteLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: int = Field(ge=1)


class SetPalette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    colors: list[HexColor] = Field(min_length=1, max_length=256)


class UndoRedo(BaseModel):
    model_config = ConfigDict(extra="forbid")


def register() -> None:
    REGISTRY.register(OpSpec("create_sprite", "session", CreateSprite,
                             lua="_mcp_op_create_sprite", mutating=True))
    REGISTRY.register(OpSpec("open_sprite", "session", OpenSprite,
                             lua="_mcp_op_open_sprite", mutating=True))
    REGISTRY.register(OpSpec("save_sprite", "session", SaveSprite,
                             lua="_mcp_op_save_sprite", mutating=True))
    REGISTRY.register(OpSpec("close_session", "session", CloseSession,
                             mutating=True, destructive=True))
    REGISTRY.register(OpSpec("add_layer", "session", AddLayer,
                             lua="_mcp_op_add_layer", mutating=True))
    REGISTRY.register(OpSpec("set_layer", "session", SetLayer,
                             lua="_mcp_op_set_layer", mutating=True))
    REGISTRY.register(OpSpec("delete_layer", "session", DeleteLayer,
                             lua="_mcp_op_delete_layer", mutating=True, destructive=True))
    REGISTRY.register(OpSpec("set_palette", "session", SetPalette,
                             lua="_mcp_op_set_palette", mutating=True))
    # Meta op: no Lua, tools.apply_operations routes it to Engine.undo/redo (spec §6.3)
    REGISTRY.register(OpSpec("undo", "meta", UndoRedo, mutating=True))
    REGISTRY.register(OpSpec("redo", "meta", UndoRedo, mutating=True))


register()
