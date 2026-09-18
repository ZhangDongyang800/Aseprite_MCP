"""会话生命周期 op（spec §5）。"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.v2.registry import OpSpec, REGISTRY


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


def register() -> None:
    REGISTRY.register(OpSpec("create_sprite", "session", CreateSprite,
                             lua="_mcp_op_create_sprite", mutating=True))
    REGISTRY.register(OpSpec("open_sprite", "session", OpenSprite,
                             lua="_mcp_op_open_sprite", mutating=True))
    REGISTRY.register(OpSpec("save_sprite", "session", SaveSprite,
                             lua="_mcp_op_save_sprite", mutating=True))
    REGISTRY.register(OpSpec("close_session", "session", CloseSession,
                             mutating=True, destructive=True))


register()
