"""execute_web_tool() — web tool dispatch"""

import json
from typing import Any

# ---- Schema definitions ----
from .schemas import WEB_TOOL_DEFINITIONS

# ---- Implementation functions ----
from .implementations import *
from wal.tools.shared.memory import save_agent_memory, get_agent_memory, delete_agent_memory


def execute_web_tool(tool_name: str, arguments: dict, project_name: str) -> str:
    """执行联网搜索工具调用，返回结果字符串

    Args:
        tool_name: "web_search" | "web_fetch" | "encyclopedia_search"
        arguments: LLM 传入的参数字典
        project_name: 项目名称（用于日志）

    Returns:
        格式化的结果字符串
    """
    from .implementations import web_search, web_fetch, suggest_alternative_urls, encyclopedia_search

    tool_map = {
        "web_search": lambda: web_search(
            query=arguments["query"],
            project_name=project_name,
            num_results=arguments.get("num_results", 5),
            language=arguments.get("language", "zh-CN"),
        ),
        "web_fetch": lambda: web_fetch(
            url=arguments["url"],
            project_name=project_name,
            max_length=arguments.get("max_length", 8000),
            offset=arguments.get("offset", 0),
        ),
        "suggest_alternative_urls": lambda: suggest_alternative_urls(
            blocked_url=arguments["blocked_url"],
        ),
        "encyclopedia_search": lambda: encyclopedia_search(
            query=arguments["query"],
            project_name=project_name,
            language=arguments.get("language", "zh-CN"),
            max_length=arguments.get("max_length", 8000),
            skip_cache=arguments.get("skip_cache", False),
            start_level=arguments.get("start_level", 0),
        ),
    }

    func = tool_map.get(tool_name)
    if not func:
        return f"[Error] Unknown web tool: {tool_name}"

    try:
        result = func()
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)
    except Exception as e:
        return f"[Tool Error] {tool_name}: {e}"
