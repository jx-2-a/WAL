"""WEB_TOOL_DEFINITIONS — web tool JSON schemas"""

WEB_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "搜索互联网获取参考资料。用于研究世界观设定（历史、地理、科技、文化等）、"
                "查证事实、寻找写作灵感。返回标题+URL+摘要，不包含完整页面内容。"
                "如需深入阅读某条结果，请用 web_fetch 抓取完整内容。"
                "⭐ 结果中标注了优先抓取来源——Wikipedia 对自动化友好，优先选择。"
                "基于 Bing (cn.bing.com)，国内直连，免费零配置。"
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
                "如果返回 403，用 suggest_alternative_urls 生成替代链接重试。"
                "⭐ Wikipedia 链接优先抓取——对自动化友好，极少被拒。"
                "支持分段读取：若返回 truncated=true，可用 next_offset 作为 offset 继续读取"
                "后续内容，就像向下滚动页面一样。"
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
                        "description": "返回最大字符数，默认8000，范围500~8000。超长内容会自动截断",
                    },
                    "offset": {
                        "type": "integer",
                        "description": (
                            "起始字符位置，默认0从开头开始。"
                            "当上一轮 web_fetch 返回 truncated=true 时，"
                            "用返回的 next_offset 值继续读取后续内容（向下滚动）。"
                            "例如：上次返回 next_offset=8000，则传 offset=8000 读第8001字符起的内容"
                        ),
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_alternative_urls",
            "description": (
                "当 web_fetch 抓取被拒（403）时，根据被封的 URL 生成替代链接。"
                "自动从 URL 提取关键词，生成 Wikipedia 等对抓取友好的替代来源。"
                "⚠️ 调用后必须立即用 web_fetch 依次尝试返回的链接，第1条失败就试第2条，不要只拿链接不抓。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "blocked_url": {
                        "type": "string",
                        "description": "被拒绝访问的 URL（即 web_fetch 返回 403 的那个链接）",
                    },
                },
                "required": ["blocked_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "encyclopedia_search",
            "description": (
                "搜索百科词条的完整正文内容。与 web_search 不同：\n"
                "  - web_search：搜整个互联网，返回标题+URL+摘要列表，适合最新信息、多方观点\n"
                "  - encyclopedia_search：搜百科网站（Wikipedia/360百科/百度百科），返回完整词条正文，"
                "适合固定知识、世界观设定参考、角色/地点/概念的定义\n\n"
                "何时用 encyclopedia_search（而非 web_search）：\n"
                "  1. 查某个具体概念/术语的定义（如'金丹'、'元婴'、'修真'）\n"
                "  2. 查历史人物、地理、文化等固定知识\n"
                "  3. 写作中需要权威、结构化的背景知识\n"
                "  4. web_search 摘要不够详细，需要完整百科词条\n\n"
                "何时用 web_search：\n"
                "  1. 查最新新闻、动态事件\n"
                "  2. 需要多方观点和来源\n"
                "  3. 百科覆盖不到的小众话题\n"
                "  4. 不确定时两个都调用，互相补充\n\n"
                "优先级链（默认 start_level=0 全链尝试）：\n"
                "  0: Wikipedia中文 → 360百科 → 百度百科 → Wikipedia英文（默认）\n"
                '  1: 360百科 → 百度百科 → Wikipedia英文（预判 Wikipedia 无独立词条时用，如"闲章"）\n'
                "  2: 百度百科 → Wikipedia英文\n"
                "  3: 仅 Wikipedia 英文\n"
                "结果自动本地缓存，同词条再次查询直接返回缓存（不消耗网络请求）。\n"
                "费用：Wikipedia 免费（MediaWiki API），百度百科 50次/天（AppBuilder API），360百科免费。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "词条关键词。建议使用最简短、最常见的词条名，如'韩立'而非'凡人修仙传韩立'",
                    },
                    "language": {
                        "type": "string",
                        "description": "语言偏好。zh-CN=中文百科优先，en=英文百科优先。默认 zh-CN",
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "返回最大字符数，默认8000，范围500~8000",
                    },
                    "skip_cache": {
                        "type": "boolean",
                        "description": "是否跳过本地缓存强制联网搜索。默认 false（优先读缓存）。当之前的缓存结果不理想时设为 true",
                    },
                    "start_level": {
                        "type": "integer",
                        "description": (
                            "从第几级开始尝试（0-3）。Wikipedia 经常对中文小众词条返回不相关结果"
                            "（如搜'闲章'返回'藏书印'），如果预判 Wikipedia 无独立词条，"
                            "设 start_level=1 跳过 Wikipedia 直接从 360 百科查起。"
                            "默认 0（全链尝试）。"
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ============================================================
#  Dispatch
# ============================================================
