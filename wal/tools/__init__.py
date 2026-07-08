"""WAL 工具系统

所有 Agent 可调用工具的定义、分发和实现。

工具按模式组织：
- shared/      跨模式共享（记忆管理）
- writing/     写作模式（~35 个工具）
- planning/    规划模式（~12 个工具）
- autonomous/  自主模式（~12 个工具）
- web/         联网搜索（4 个工具）

用法：
    from wal.tools.writing import TOOL_DEFINITIONS, execute_tool
    from wal.tools.web import WEB_TOOL_DEFINITIONS, execute_web_tool

向后兼容（旧路径仍可用但推荐用新路径）：
    from wal.agent.tool_defs import TOOL_DEFINITIONS  # deprecated
"""

from .writing import TOOL_DEFINITIONS, execute_tool
from .planning import PLAN_TOOL_DEFINITIONS, execute_plan_tool
from .autonomous import AUTO_TOOL_DEFINITIONS, execute_auto_tool
from .web import WEB_TOOL_DEFINITIONS, execute_web_tool
from .shared import save_agent_memory, get_agent_memory, delete_agent_memory

__all__ = [
    "TOOL_DEFINITIONS", "execute_tool",
    "PLAN_TOOL_DEFINITIONS", "execute_plan_tool",
    "AUTO_TOOL_DEFINITIONS", "execute_auto_tool",
    "WEB_TOOL_DEFINITIONS", "execute_web_tool",
    "save_agent_memory", "get_agent_memory", "delete_agent_memory",
]
