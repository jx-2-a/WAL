"""自主模式工具 — 控制 Agent 自主写作行为"""

from .schemas import AUTO_TOOL_DEFINITIONS
from .dispatch import execute_auto_tool

__all__ = ["AUTO_TOOL_DEFINITIONS", "execute_auto_tool"]
