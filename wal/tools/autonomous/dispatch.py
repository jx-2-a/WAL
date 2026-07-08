"""execute_auto_tool() — autonomous tool dispatch"""

import json
from typing import Any

# ---- Schema definitions ----
from .schemas import AUTO_TOOL_DEFINITIONS

# ---- Implementation functions ----
from .implementations import *
from wal.tools.shared.memory import save_agent_memory, get_agent_memory, delete_agent_memory


def execute_auto_tool(tool_name: str, arguments: dict, project_name: str) -> str:
    """执行自主模式工具调用，返回结果字符串"""
    from .implementations import (
        set_autonomy_level,
        set_direction,
        start_auto_session,
        end_auto_session,
        create_checkpoint,
        rollback_to_checkpoint,
        list_checkpoints,
        approve_decision,
        reject_decision,
        get_auto_status,
    )
    from wal.tools.shared.memory import save_agent_memory, get_agent_memory

    tool_map = {
        "set_autonomy_level": lambda: set_autonomy_level(
            project_name, arguments["level"]),
        "set_direction": lambda: set_direction(
            project_name, arguments["direction"]),
        "start_auto_session": lambda: start_auto_session(
            project_name,
            arguments.get("direction", ""),
            arguments.get("chapter_start", 0),
        ),
        "end_auto_session": lambda: end_auto_session(project_name),
        "create_checkpoint": lambda: create_checkpoint(
            project_name,
            arguments["label"],
            arguments.get("description", ""),
            arguments.get("chapter_number", 0),
        ),
        "rollback_to_checkpoint": lambda: rollback_to_checkpoint(
            project_name, arguments["label"]),
        "list_checkpoints": lambda: list_checkpoints(project_name),
        "approve_decision": lambda: approve_decision(
            project_name, arguments["decision_id"]),
        "reject_decision": lambda: reject_decision(
            project_name, arguments["decision_id"]),
        "get_auto_status": lambda: get_auto_status(project_name),
        # 跨模式工具
        "switch_mode": lambda: f"[Internal] switch_mode is handled by AgentLoop pre-dispatch",
        # 持久记忆
        "save_agent_memory": lambda: save_agent_memory(
            project_name,
            arguments["key"],
            arguments["value"],
        ),
        "get_agent_memory": lambda: get_agent_memory(
            project_name,
            arguments.get("key", ""),
        ),
    }

    func = tool_map.get(tool_name)
    if not func:
        return f"[Error] Unknown auto tool: {tool_name}"

    try:
        result = func()
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)
    except Exception as e:
        return f"[Tool Error] {tool_name}: {e}"
