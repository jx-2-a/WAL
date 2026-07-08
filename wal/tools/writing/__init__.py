"""写作模式工具 — Agent 可直接调用的写作辅助接口"""

from .schemas import TOOL_DEFINITIONS
from .dispatch import execute_tool

__all__ = ["TOOL_DEFINITIONS", "execute_tool"]
