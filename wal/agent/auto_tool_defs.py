"""自主模式工具定义 — 10 个自主工具的 OpenAI Function Calling schema"""

import json
from pathlib import Path
from typing import Any

AUTO_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "set_autonomy_level",
            "description": "设置自主等级：suggest_only（仅建议）/ auto_minor（小修改自动执行）/ auto_moderate（可写场景和添加元素）/ full_auto（完全自主）",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["suggest_only", "auto_minor", "auto_moderate", "full_auto"],
                        "description": "自主等级",
                    },
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_direction",
            "description": "设置自主写作方向/目标，如「完成第3卷的5章内容」「推进叶凡的成长线」",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "自主写作方向描述",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_auto_session",
            "description": "开始自主写作会话。需要先设置 autonomy_level 和 direction。开始后会追踪写入章节数和决策记录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "写作方向（可选，会覆盖之前的设置）",
                    },
                    "chapter_start": {
                        "type": "integer",
                        "description": "起始章节号（可选）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_auto_session",
            "description": "结束自主写作会话，输出统计：总决策数、已审批数、写入章节数",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_checkpoint",
            "description": "创建数据库检查点（wal.db 快照），用于在自主批量操作前备份。检查点文件保存在 checkpoints/ 目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "检查点标签（字母数字下划线），如 before_ch3_rewrite",
                    },
                    "description": {
                        "type": "string",
                        "description": "检查点描述（可选）",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "当前章节号，记录到检查点元数据",
                    },
                },
                "required": ["label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_to_checkpoint",
            "description": "回滚到指定检查点（恢复 wal.db）。回滚前会自动创建检查点作为安全备份。",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "要回滚到的检查点标签",
                    },
                },
                "required": ["label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_checkpoints",
            "description": "列出所有已创建的检查点，按时间倒序。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_decision",
            "description": "审批通过一条自主决策。审批后 Agent 可以执行该决策中的操作。通常用于 moderate/major/critical 级别的决策。",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision_id": {
                        "type": "string",
                        "description": "决策ID，如 ad_0001",
                    },
                },
                "required": ["decision_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_decision",
            "description": "拒绝一条自主决策。",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision_id": {
                        "type": "string",
                        "description": "决策ID，如 ad_0001",
                    },
                },
                "required": ["decision_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_auto_status",
            "description": "获取自主模式当前状态：运行状态、自主等级、方向、决策统计、待审批决策列表、检查点数量",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_mode",
            "description": "切换 Agent 工作模式。自主写作中如需先分析再写，可切到 planning 分析后切回 autonomous。",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["writing", "planning", "autonomous"],
                        "description": "目标模式",
                    },
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_agent_memory",
            "description": "保存一条持久记忆（key-value）。记录重要的写作决策、转折点、用户偏好等，重启后仍存在。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "记忆键名",
                    },
                    "value": {
                        "type": "string",
                        "description": "要保存的内容",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_memory",
            "description": "读取保存的持久记忆。key 为空时列出所有记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "要读取的记忆键名。留空列出全部",
                    },
                },
                "required": [],
            },
        },
    },
]


def execute_auto_tool(tool_name: str, arguments: dict, project_name: str) -> str:
    """执行自主模式工具调用，返回结果字符串"""
    from wal.agent.auto_tools import (
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
    from wal.agent.memory_tools import save_agent_memory, get_agent_memory

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
