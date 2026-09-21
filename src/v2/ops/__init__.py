"""导入即注册所有内置 op。"""

from src.v2.ops import draw_ops, session_ops, structure_ops  # noqa: F401

from src.v2.registry import REGISTRY  # re-export

__all__ = ["REGISTRY"]
