"""联网搜索工具 — web_search, web_fetch, encyclopedia_search 等"""

from .schemas import WEB_TOOL_DEFINITIONS
from .dispatch import execute_web_tool

__all__ = ["WEB_TOOL_DEFINITIONS", "execute_web_tool"]
