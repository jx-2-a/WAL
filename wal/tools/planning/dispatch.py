"""execute_plan_tool() — planning tool dispatch"""

import json
from typing import Any

# ---- Schema definitions ----
from .schemas import PLAN_TOOL_DEFINITIONS

# ---- Implementation functions ----
from .implementations import *
from wal.tools.shared.memory import save_agent_memory, get_agent_memory, delete_agent_memory


def execute_plan_tool(tool_name: str, arguments: dict, project_name: str) -> str:
    """执行规划工具调用，返回结果字符串"""
    import os
    from pathlib import Path
    from .implementations import (
        suggest_plot_direction,
        brainstorm_character_arc,
        analyze_plot_holes,
        propose_plot_twist,
        evaluate_pacing,
        suggest_conflict_escalation,
        brainstorm_world_building,
        analyze_theme_consistency,
        add_planning_note,
        list_planning_notes,
        get_planning_note,
    )
    from wal.tools.shared.memory import save_agent_memory, get_agent_memory

    tool_map = {
        "suggest_plot_direction": lambda: suggest_plot_direction(
            project_name,
            arguments.get("context", ""),
            arguments.get("count", 3),
        ),
        "brainstorm_character_arc": lambda: brainstorm_character_arc(
            project_name,
            arguments.get("char_id", ""),
            arguments.get("char_name", ""),
            arguments.get("focus", ""),
        ),
        "analyze_plot_holes": lambda: analyze_plot_holes(
            project_name,
            arguments.get("deep", False),
        ),
        "propose_plot_twist": lambda: propose_plot_twist(
            project_name,
            arguments.get("context", ""),
            arguments.get("twist_type", ""),
        ),
        "evaluate_pacing": lambda: evaluate_pacing(
            project_name,
            arguments.get("start_chapter", 0),
            arguments.get("end_chapter", 0),
        ),
        "suggest_conflict_escalation": lambda: suggest_conflict_escalation(
            project_name,
            arguments.get("conflict_type", ""),
            arguments.get("chapter_number", 0),
        ),
        "brainstorm_world_building": lambda: brainstorm_world_building(
            project_name,
            arguments.get("aspect", ""),
            arguments.get("chapter_number", 0),
        ),
        "analyze_theme_consistency": lambda: analyze_theme_consistency(
            project_name,
            arguments.get("theme", ""),
        ),
        # 规划笔记持久化
        "add_planning_note": lambda: add_planning_note(
            project_name,
            arguments["title"],
            arguments.get("category", ""),
            arguments.get("content", ""),
            arguments.get("decisions", ""),
            arguments.get("related_tools", []),
        ),
        "list_planning_notes": lambda: list_planning_notes(
            project_name,
            arguments.get("category", ""),
            arguments.get("limit", 20),
        ),
        "get_planning_note": lambda: get_planning_note(
            project_name,
            arguments["note_id"],
        ),
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
        return f"[Error] Unknown plan tool: {tool_name}"

    try:
        result = func()
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)
    except Exception as e:
        return f"[Tool Error] {tool_name}: {e}"
