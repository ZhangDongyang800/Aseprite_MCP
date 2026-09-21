"""文档结构 op：加帧、设每帧时长、给帧区间命名。"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.v2.registry import OpSpec, REGISTRY

MAX_SECONDS = 60


class AddFrames(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1, le=256)
    duration: float = Field(default=0.1, gt=0, le=MAX_SECONDS)
    duplicate: bool = False


class SetDurations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    durations: list[float] = Field(min_length=1, max_length=256)

    @field_validator("durations")
    @classmethod
    def _in_range(cls, values: list[float]) -> list[float]:
        bad = next((v for v in values if not 0 < v <= MAX_SECONDS), None)
        if bad is not None:
            raise ValueError(f"every duration is in seconds: 0 < {bad} <= {MAX_SECONDS}")
        return values


class AddTag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    from_frame: int = Field(ge=1)
    to_frame: int = Field(ge=1)


def register() -> None:
    REGISTRY.register(OpSpec("add_frames", "structure", AddFrames,
                             lua="_mcp_op_add_frames", mutating=True))
    REGISTRY.register(OpSpec("set_durations", "structure", SetDurations,
                             lua="_mcp_op_set_durations", mutating=True))
    REGISTRY.register(OpSpec("add_tag", "structure", AddTag,
                             lua="_mcp_op_add_tag", mutating=True))


register()
