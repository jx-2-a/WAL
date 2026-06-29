"""联网搜索工具定义 — OpenAI Function Calling 格式的 schema + dispatch

提供两个工具：
  - web_search: 搜索互联网获取参考资料摘要（默认 DuckDuckGo Lite，可选 SearXNG）
  - web_fetch: 抓取指定 URL 的页面正文（基于 trafilatura）

DuckDuckGo Lite 为零配置默认后端，无需 API Key 或 Docker。
设置 SEARXNG_INSTANCE 环境变量后自动切换为 SearXNG 聚合搜索（Google/Bing/DDG 等）。
"""

import json
from typing import Any

# ============================================================
#  工具 JSON Schema 定义
# ============================================================

WEB_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "搜索互联网获取参考资料。用于研究世界观设定（历史、地理、科技、文化等）、"
                "查证事实、寻找写作灵感。返回标题+URL+摘要，不包含完整页面内容。"
                "如需深入阅读某条结果，请用 web_fetch 抓取完整内容。"
                "基于 DuckDuckGo Lite，完全免费，零配置。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词。建议使用具体、描述性的查询以提高相关性。",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "返回结果数量，默认5，最大10",
                    },
                    "language": {
                        "type": "string",
                        "description": "语言偏好。zh-CN=中文优先，en=英文优先，留空=不限制。默认 zh-CN",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "抓取指定 URL 的页面正文内容。用于深入阅读 web_search 找到的参考页面。"
                "自动提取正文（去除导航/广告等噪音），返回纯文本。"
                "适合获取详细的世界观资料、历史记载、科学解释等长文内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要抓取的页面 URL，必须以 http:// 或 https:// 开头",
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "返回最大字符数，默认3000，最大8000。超长内容会自动截断",
                    },
                },
                "required": ["url"],
            },
        },
    },
]


# ============================================================
#  Dispatch
# ============================================================

def execute_web_tool(tool_name: str, arguments: dict, project_name: str) -> str:
    """执行联网搜索工具调用，返回结果字符串

    Args:
        tool_name: "web_search" | "web_fetch"
        arguments: LLM 传入的参数字典
        project_name: 项目名称（用于日志）

    Returns:
        格式化的结果字符串
    """
    from wal.agent.web_tools import web_search, web_fetch

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
            max_length=arguments.get("max_length", 3000),
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
