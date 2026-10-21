"""文件导出 op：把会话里的精灵写成交付物，不改文档。"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.v2.registry import OpSpec, REGISTRY


class Export(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["png", "gif", "sheet", "frames"] = "png"
    output: str = Field(min_length=1)
    scale: int = Field(default=1, ge=1, le=64)
    frame: Optional[int] = Field(default=None, ge=1)
    tag: Optional[str] = Field(default=None, max_length=64)
    layout: Literal["horizontal", "vertical", "rows", "columns"] = "horizontal"
    columns: int = Field(default=0, ge=0, le=256)
    padding: int = Field(default=0, ge=0, le=64)

    @model_validator(mode="after")
    def _check_contract(self):
        # CLI and Live mode can have different Aseprite working directories; resolve once
        # here so the file Aseprite writes and the path Python verifies are the same one.
        self.output = str(Path(self.output).expanduser().resolve())
        expected = ".gif" if self.format == "gif" else ".png"
        if not self.output.lower().endswith(expected):
            raise ValueError(f"format={self.format} requires output ending in {expected}")
        if self.format != "png" and self.frame is not None:
            raise ValueError("frame is only valid for format='png'")
        if self.format == "png" and self.tag:
            raise ValueError("tag is only valid for format='gif', 'sheet' or 'frames'")
        return self


def register() -> None:
    # 只写文件，不改文档：不触发快照/保存，也不占用 undo。
    REGISTRY.register(OpSpec("export", "export", Export,
                             lua="_mcp_op_export", mutating=False))


register()
