"""Agent 工具定义 — OpenAI Function Calling 格式的工具 schema 及执行映射"""

import json
from pathlib import Path
from typing import Any

# 工具 JSON Schema 定义（OpenAI Function Calling 格式）
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_story_status",
            "description": "查看当前小说的整体状态：章节数、完成度、总字数、进度百分比",
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
            "name": "get_chapter_context",
            "description": "获取指定章节的完整写作上下文，包括剧情任务、出场角色、支线提醒、前一章摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter": {
                        "type": "integer",
                        "description": "章节号，例如 1, 2, 3",
                    },
                },
                "required": ["chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dangling_plots",
            "description": "列出所有未收束（未完成）的支线剧情，帮助避免遗漏伏笔",
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
            "name": "list_characters",
            "description": "列出小说中所有角色，可按角色类型过滤",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["protagonist", "antagonist", "supporting", "minor"],
                        "description": "角色类型过滤（可选）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_character",
            "description": "获取某个角色的完整档案：性格、背景、动机、能力、弱点、关系",
            "parameters": {
                "type": "object",
                "properties": {
                    "char_id": {
                        "type": "string",
                        "description": "角色ID，例如 char_001",
                    },
                },
                "required": ["char_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_plot_lines",
            "description": "列出所有剧情线（主线和支线）的名称、类型、完成进度",
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
            "name": "plot_health_check",
            "description": "检查主线支线交织健康度：是否有支线未与主线交汇、是否有情节点未分配章节",
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
            "name": "write_scene_content",
            "description": "将撰写好的场景正文保存到指定章节的指定场景",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "scene_index": {
                        "type": "integer",
                        "description": "场景在章节中的索引（从0开始）",
                    },
                    "content": {
                        "type": "string",
                        "description": "场景正文内容",
                    },
                },
                "required": ["chapter", "scene_index", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_plot_point",
            "description": "更新某个剧情点的状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_id": {
                        "type": "string",
                        "description": "剧情线ID，例如 plot_001",
                    },
                    "point_id": {
                        "type": "string",
                        "description": "情节点ID，例如 plot_001_pp001",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "done"],
                        "description": "新状态",
                    },
                },
                "required": ["plot_id", "point_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_next_scene",
            "description": "基于当前剧情状态，给出下一场景的写作建议",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter": {
                        "type": "integer",
                        "description": "章节号",
                    },
                },
                "required": ["chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "export_outline",
            "description": "导出整部小说的大纲，包括所有章节标题、摘要、字数",
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
            "name": "character_relationship_map",
            "description": "获取所有角色之间的关系图谱，显示谁和谁是什么关系",
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
            "name": "add_chapter",
            "description": "向故事添加新章节。不指定章节号则自动追加到末尾。指定章节号时必须唯一，且该号未被占用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "章节标题",
                    },
                    "summary": {
                        "type": "string",
                        "description": "章节内容摘要",
                    },
                    "word_count_target": {
                        "type": "integer",
                        "description": "目标字数，默认3000",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号（可选）。不填则自动追加到末尾。指定时如已被占用会报错",
                    },
                    "volume_id": {
                        "type": "string",
                        "description": "所属卷ID，如 vol_001（可选）",
                    },
                    "volume_number": {
                        "type": "integer",
                        "description": "所属卷序号（可选，volume_id 优先）",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_character",
            "description": "向故事添加新角色",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色姓名",
                    },
                    "role": {
                        "type": "string",
                        "enum": ["protagonist", "antagonist", "supporting", "minor"],
                        "description": "角色定位",
                    },
                    "background_story": {
                        "type": "string",
                        "description": "背景故事",
                    },
                    "motivation": {
                        "type": "string",
                        "description": "核心动机",
                    },
                    "personality_traits": {
                        "type": "string",
                        "description": "性格特征，逗号分隔",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_volume_context",
            "description": "获取指定卷的完整写作上下文：卷主题、摘要、章节列表及各自进度、伏笔状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_id": {
                        "type": "string",
                        "description": "卷ID，如 vol_001",
                    },
                },
                "required": ["volume_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_volumes",
            "description": "列出故事中所有卷的序号、标题、主题、章节数、完成进度",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_id": {
                        "type": "string",
                        "description": "部ID（可选），过滤指定部下的卷",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plot_tree",
            "description": "获取剧情层级树：主线→卷主线→支线→角色弧光，显示完整的嵌套结构和各自进度",
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
            "name": "add_foreshadowing",
            "description": "添加一个新伏笔：记录伏笔描述、所属章节、计划回收章节、紧急程度，可关联剧情线和角色",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "伏笔描述",
                    },
                    "created_at_chapter": {
                        "type": "integer",
                        "description": "埋设伏笔的章节号，默认为0",
                    },
                    "target_chapter": {
                        "type": "integer",
                        "description": "计划回收伏笔的章节号，默认为0",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "紧急程度",
                    },
                    "related_plot_lines": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关联的剧情线ID列表",
                    },
                    "related_characters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关联的角色ID列表",
                    },
                    "notes": {
                        "type": "string",
                        "description": "备注",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_foreshadowing",
            "description": "回收（标记为已解决）一个伏笔，记录回收章节和说明",
            "parameters": {
                "type": "object",
                "properties": {
                    "fw_id": {
                        "type": "string",
                        "description": "伏笔ID，例如 fw_001",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "回收伏笔的章节号",
                    },
                    "notes": {
                        "type": "string",
                        "description": "回收说明（可选）",
                    },
                },
                "required": ["fw_id", "chapter_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_foreshadowing_health",
            "description": "伏笔健康检查：统计伏笔总数、已回收数、紧急/高优先级未回收数、长期未回收数",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_chapter": {
                        "type": "integer",
                        "description": "当前章节号，用于计算伏笔已埋多久",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_character_snapshot",
            "description": "为角色在指定章节创建状态快照：记录弧光进度、性格/外貌变化、新能力、关系变化、内心状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "char_id": {
                        "type": "string",
                        "description": "角色ID，例如 char_001",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "chapter_title": {
                        "type": "string",
                        "description": "章节标题（可选）",
                    },
                    "arc_progress": {
                        "type": "string",
                        "description": "弧光进度描述",
                    },
                    "personality_changes": {
                        "type": "string",
                        "description": "性格变化（如'变得更加果断'）",
                    },
                    "new_abilities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新获得的能力",
                    },
                    "internal_state": {
                        "type": "string",
                        "description": "内心状态描述",
                    },
                    "summary": {
                        "type": "string",
                        "description": "本章角色总结",
                    },
                },
                "required": ["char_id", "chapter_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_character_evolution",
            "description": "获取角色的完整演变历程：每章的弧光进度、性格变化、能力增减",
            "parameters": {
                "type": "object",
                "properties": {
                    "char_id": {
                        "type": "string",
                        "description": "角色ID，例如 char_001",
                    },
                },
                "required": ["char_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_story_index",
            "description": "全文搜索故事内容（FTS5）：搜索所有已索引的章节场景，返回高亮匹配片段。支持多关键词和模糊搜索",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，支持 FTS5 语法：'keyword1 AND keyword2'、'keyword*' 等",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量上限，默认20",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chapter_summary",
            "description": "生成章节的结构化摘要：字数统计、出场角色、涉及地点、剧情点、关键词索引",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                },
                "required": ["chapter_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quick_review",
            "description": "快速回顾某段章节范围的内容：章节摘要列表 + 可选的 FTS5 主题搜索。适合「回顾30-40章关于叶凡的剧情」",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_chapter": {
                        "type": "integer",
                        "description": "起始章节号",
                    },
                    "end_chapter": {
                        "type": "integer",
                        "description": "结束章节号",
                    },
                    "topic": {
                        "type": "string",
                        "description": "回顾主题/关键词（可选），指定后同时进行全文搜索",
                    },
                },
                "required": ["start_chapter", "end_chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "export_chapter",
            "description": "导出章节/卷/全书为 Markdown、HTML 或纯文本。可导出单章、批量章节范围或整部小说",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号（单章导出时必填）",
                    },
                    "start_chapter": {
                        "type": "integer",
                        "description": "起始章节号（批量导出时使用）",
                    },
                    "end_chapter": {
                        "type": "integer",
                        "description": "结束章节号（批量导出时使用）",
                    },
                    "volume_number": {
                        "type": "integer",
                        "description": "卷序号（卷导出时使用）",
                    },
                    "full_novel": {
                        "type": "boolean",
                        "description": "是否导出全书（true 时忽略其他参数）",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "html", "plain"],
                        "description": "导出格式，默认 markdown",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "export_yaml_backup",
            "description": "将 SQLite 数据库导出为 YAML 文件备份（story.yaml, characters.yaml, plot_lines.yaml）。用于数据可读备份和跨系统迁移",
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
            "name": "delete_chapter",
            "description": "删除指定章节及其所有场景。会同时清理全文索引。用于清理空章节、测试章节或重复章节。删除后章节序号不变。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "要删除的章节号",
                    },
                },
                "required": ["chapter_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_chapter_status",
            "description": "设置章节状态：draft（草稿）/ writing（写作中）/ done（完成）。写完后标记为 done，方便追踪进度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["draft", "writing", "done"],
                        "description": "新状态",
                    },
                },
                "required": ["chapter_number", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_chapter_info",
            "description": "更新章节的元信息（标题、摘要、备注、目标字数）。只更新传入的非空字段，其他字段保持不变。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "title": {
                        "type": "string",
                        "description": "新标题（可选，不传则保持不变）",
                    },
                    "summary": {
                        "type": "string",
                        "description": "新摘要（可选）",
                    },
                    "notes": {
                        "type": "string",
                        "description": "新备注（可选）",
                    },
                    "word_count_target": {
                        "type": "integer",
                        "description": "新目标字数（可选）",
                    },
                },
                "required": ["chapter_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_volume",
            "description": "添加新卷。卷是章节的组织单位，所有章节都应归属到某个卷下。可指定所属部（Part）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "卷标题（如：初入江湖）",
                    },
                    "part_id": {
                        "type": "string",
                        "description": "所属部ID（可选，如 part_001）",
                    },
                    "summary": {
                        "type": "string",
                        "description": "卷摘要（可选）",
                    },
                    "theme": {
                        "type": "string",
                        "description": "卷主题（可选）",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_volume",
            "description": "删除指定卷及其所有章节和场景。会同时清理卷下所有章节、场景内容和FTS索引。用于清理空卷、测试卷或误创建的卷。",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_id": {
                        "type": "string",
                        "description": "要删除的卷ID（如 vol_001）",
                    },
                },
                "required": ["volume_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_plot_line",
            "description": "删除指定剧情线及其下所有情节点。用于清理重复、错误或废弃的剧情线。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_id": {
                        "type": "string",
                        "description": "要删除的剧情线ID（如 plot_001）",
                    },
                },
                "required": ["plot_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_character",
            "description": "删除指定角色及其所有关系记录。支持按角色ID或角色名查找。会同时清理该角色关联的所有人际关系。",
            "parameters": {
                "type": "object",
                "properties": {
                    "char_id": {
                        "type": "string",
                        "description": "要删除的角色ID（如 char_001）或角色名",
                    },
                },
                "required": ["char_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_scene",
            "description": "删除章节中的指定场景。会同时清理全文索引。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "scene_index": {
                        "type": "integer",
                        "description": "场景索引（从0开始）",
                    },
                },
                "required": ["chapter_number", "scene_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "export_novel_files",
            "description": "导出正文到磁盘文件。支持按卷分文件夹、单章平铺，或全书合并为单个文件（总集）。支持 plain/markdown/html/docx 四种格式。docx 格式自带中文排版（微软雅黑12pt，首行缩进，1.5倍行距），不含章节摘要（纯读者版）。structure='flat' 可跳过卷标题直接输出章节，适合纯阅读。推荐在每写完一卷后调用一次。",
            "parameters": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "输出根目录的绝对路径。如不指定则默认导出到 projects/<项目名>/export/",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["volume", "chapter", "single", "auto"],
                        "description": "组织方式：volume=每卷一个文件夹(推荐，大小适中)；chapter=所有章节平铺在一个文件夹下；single=全书合并为一个文件（总集，适合出书/打印/投稿）；auto=自动判断（≤30章用chapter，>30章用volume）。默认 volume",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["plain", "markdown", "html", "docx"],
                        "description": "导出格式：plain=纯文本(.txt，适合网文阅读)；markdown=MD格式(.md)；html=网页格式；docx=Word文档(.docx，中文排版，适合打印/投稿/交稿)。默认 plain",
                    },
                    "structure": {
                        "type": "string",
                        "enum": ["full", "flat"],
                        "description": "内部结构（仅 mode='single' 时生效）：full=完整层级含部/卷标题（默认，适合有复杂结构的作品）；flat=纯章节排列无卷标题（简洁，直接阅读）。默认 full",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_mode",
            "description": "切换 Agent 工作模式。planning=分析规划（只读分析工具），writing=内容创作（全量写作工具），autonomous=自主批量写作。分析/规划完成后应切换到 writing 执行，需要分析时切回 planning。",
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
            "description": "保存一条 key-value 持久记忆。用于记录重要的讨论结论、用户偏好、写作决策等，重启后依然存在。记得定期用此工具保存关键上下文，防止对话压缩丢失。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "记忆键名，如 'chapter_5_decisions', 'user_preferred_style', 'main_conflict_notes'",
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
            "description": "读取保存的持久记忆。key 为空时列出所有已保存的记忆。用于在对话开始或切换上下文时回顾之前的重要结论。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "要读取的记忆键名。留空则列出所有记忆的键和摘要。",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_plot_line",
            "description": "创建一条新剧情线（主线/支线/卷主线/角色弧光）。剧情线用于组织和管理故事结构，每条线包含多个情节点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "剧情线名称，如「叶凡复仇线」「宗门内斗线」",
                    },
                    "plot_type": {
                        "type": "string",
                        "enum": ["main", "sub"],
                        "description": "剧情线类型：main=主线，sub=支线。默认 sub",
                    },
                    "description": {
                        "type": "string",
                        "description": "剧情线概要描述",
                    },
                    "theme": {
                        "type": "string",
                        "description": "主题/核心冲突",
                    },
                    "level": {
                        "type": "string",
                        "enum": ["main", "volume", "sub", "character_arc"],
                        "description": "层级：main=主线，volume=卷主线，sub=支线，character_arc=角色弧光",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "父剧情线ID（如 plot_001），用于建立层级关系",
                    },
                    "started_in_chapter": {
                        "type": "integer",
                        "description": "起始章节号，默认1",
                    },
                    "target_chapter": {
                        "type": "integer",
                        "description": "目标完成章节号",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_story_info",
            "description": "更新故事基本信息：书名、作者、简介、类型、标签、状态等。只更新传入的非空字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "书名",
                    },
                    "author": {
                        "type": "string",
                        "description": "作者名",
                    },
                    "summary": {
                        "type": "string",
                        "description": "故事简介/概要",
                    },
                    "genre": {
                        "type": "string",
                        "description": "类型/流派，如「玄幻」「都市」「仙侠」",
                    },
                    "tags": {
                        "type": "string",
                        "description": "标签，逗号分隔，如「穿越,系统流,扮猪吃虎」",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["planning", "writing", "done"],
                        "description": "故事状态：planning=规划中，writing=写作中，done=已完成",
                    },
                    "notes": {
                        "type": "string",
                        "description": "全局备注",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_character_relationship",
            "description": "在两个角色之间建立关系。关系类型包括：朋友、敌人、恋人、家人、师徒等。两个角色都必须已存在。",
            "parameters": {
                "type": "object",
                "properties": {
                    "char_a": {
                        "type": "string",
                        "description": "角色A的ID（如 char_001）或名称",
                    },
                    "char_b": {
                        "type": "string",
                        "description": "角色B的ID（如 char_002）或名称",
                    },
                    "rel_type": {
                        "type": "string",
                        "description": "关系类型：friend/enemy/lover/family/master/student/rival/ally/other",
                    },
                    "description": {
                        "type": "string",
                        "description": "关系描述，如「叶凡的生死之交」「互相看不顺眼的竞争对手」",
                    },
                    "dynamics": {
                        "type": "string",
                        "description": "关系动态变化，如「最初敌对，后和解」「感情逐渐升温」",
                    },
                    "history": {
                        "type": "string",
                        "description": "关系历史/往事",
                    },
                },
                "required": ["char_a", "char_b", "rel_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_custom_document",
            "description": "创建一篇自定义文档。用于存储无法格式化的自由文本：世界观细节、设定资料、灵感碎片、写作笔记等。支持分类和标签以便检索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "文档标题",
                    },
                    "category": {
                        "type": "string",
                        "description": "分类标签：world_setting/character_notes/plot_ideas/inspiration/research/other",
                    },
                    "content": {
                        "type": "string",
                        "description": "文档正文内容",
                    },
                    "tags": {
                        "type": "string",
                        "description": "标签，逗号分隔，如「修炼体系,丹药,境界划分」",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_custom_document",
            "description": "获取一篇自定义文档的完整内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "文档ID，如 cd_a1b2c3d4",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_custom_documents",
            "description": "列出所有自定义文档的摘要（标题+分类+前100字+标签）。可按分类过滤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "按分类过滤（可选，不传则列出全部）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数上限，默认20",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_custom_document",
            "description": "更新一篇自定义文档的内容。只更新传入的非空字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "文档ID，如 cd_a1b2c3d4",
                    },
                    "title": {
                        "type": "string",
                        "description": "新标题（可选）",
                    },
                    "category": {
                        "type": "string",
                        "description": "新分类（可选）",
                    },
                    "content": {
                        "type": "string",
                        "description": "新正文内容（可选）",
                    },
                    "tags": {
                        "type": "string",
                        "description": "新标签，逗号分隔（可选）",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_custom_document",
            "description": "删除一篇自定义文档。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "文档ID，如 cd_a1b2c3d4",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
]


def execute_tool(tool_name: str, arguments: dict, project_name: str) -> str:
    """执行工具调用，返回结果字符串

    根据 tool_name 从 wal.agent.tools 中找到对应函数并调用。
    """
    import os
    from wal.agent.tools import (
        get_story_status,
        get_chapter_context_text,
        list_dangling_plots,
        list_characters,
        get_character,
        list_plot_lines,
        plot_health_check,
        write_scene_content,
        update_plot_point,
        suggest_next_scene,
        export_outline,
        character_relationship_map,
        get_volume_context,
        list_volumes,
        get_plot_tree,
        add_foreshadowing,
        resolve_foreshadowing,
        check_foreshadowing_health,
        create_character_snapshot,
        get_character_evolution,
        search_story_index,
        generate_chapter_summary,
        quick_review,
        export_chapter_content,
        export_yaml_backup,
        export_novel_files,
        delete_chapter,
        set_chapter_status,
        update_chapter_info,
        add_volume_tool,
        delete_volume_tool,
        delete_plot_line_tool,
        delete_character_tool,
        delete_scene_tool,
    )
    from wal.agent.memory_tools import save_agent_memory, get_agent_memory
    from wal.core import StoryManager, CharacterManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)

    # 工具→函数映射
    tool_map = {
        "get_story_status": lambda: get_story_status(project_name),
        "get_chapter_context": lambda: get_chapter_context_text(project_name, arguments["chapter"]),
        "list_dangling_plots": lambda: list_dangling_plots(project_name),
        "list_characters": lambda: list_characters(project_name, arguments.get("role")),
        "get_character": lambda: get_character(project_name, arguments["char_id"]),
        "list_plot_lines": lambda: list_plot_lines(project_name),
        "plot_health_check": lambda: plot_health_check(project_name),
        "write_scene_content": lambda: write_scene_content(
            project_name,
            arguments["chapter"],
            arguments["scene_index"],
            arguments["content"],
        ),
        "update_plot_point": lambda: update_plot_point(
            project_name,
            arguments["plot_id"],
            arguments["point_id"],
            arguments["status"],
        ),
        "suggest_next_scene": lambda: suggest_next_scene(project_name, arguments["chapter"]),
        "export_outline": lambda: export_outline(project_name),
        "character_relationship_map": lambda: character_relationship_map(project_name),
        "get_volume_context": lambda: get_volume_context(project_name, arguments["volume_id"]),
        "list_volumes": lambda: list_volumes(project_name, arguments.get("part_id", "")),
        "get_plot_tree": lambda: get_plot_tree(project_name),
        "add_foreshadowing": lambda: add_foreshadowing(
            project_name,
            arguments["description"],
            arguments.get("created_at_chapter", 0),
            arguments.get("target_chapter", 0),
            arguments.get("urgency", "medium"),
            arguments.get("related_plot_lines", []),
            arguments.get("related_characters", []),
            arguments.get("notes", ""),
        ),
        "resolve_foreshadowing": lambda: resolve_foreshadowing(
            project_name,
            arguments["fw_id"],
            arguments["chapter_number"],
            arguments.get("notes", ""),
        ),
        "check_foreshadowing_health": lambda: check_foreshadowing_health(
            project_name,
            arguments.get("current_chapter", 0),
        ),
        "create_character_snapshot": lambda: create_character_snapshot(
            project_name,
            arguments["char_id"],
            arguments["chapter_number"],
            arguments.get("chapter_title", ""),
            arguments.get("arc_progress", ""),
            arguments.get("personality_changes", ""),
            arguments.get("new_abilities", []),
            arguments.get("internal_state", ""),
            arguments.get("summary", ""),
        ),
        "get_character_evolution": lambda: get_character_evolution(
            project_name,
            arguments["char_id"],
        ),
        "search_story_index": lambda: search_story_index(
            project_name,
            arguments["query"],
            arguments.get("limit", 20),
        ),
        "generate_chapter_summary": lambda: generate_chapter_summary(
            project_name,
            arguments["chapter_number"],
        ),
        "quick_review": lambda: quick_review(
            project_name,
            arguments["start_chapter"],
            arguments["end_chapter"],
            arguments.get("topic", ""),
        ),
        "export_chapter": lambda: export_chapter_content(
            project_name,
            arguments.get("chapter_number", 0),
            arguments.get("start_chapter", 0),
            arguments.get("end_chapter", 0),
            arguments.get("volume_number", 0),
            arguments.get("full_novel", False),
            arguments.get("format", "markdown"),
        ),
        # Extra tools defined inline
        "add_chapter": lambda: _add_chapter(project_name, arguments),
        "add_character": lambda: _add_character(project_name, arguments),
        "export_yaml_backup": lambda: export_yaml_backup(project_name),
        "export_novel_files": lambda: export_novel_files(
            project_name,
            arguments.get("output_dir", ""),
            arguments.get("mode", "volume"),
            arguments.get("format", "plain"),
            arguments.get("structure", "full"),
        ),
        "delete_chapter": lambda: delete_chapter(
            project_name,
            arguments["chapter_number"],
        ),
        "set_chapter_status": lambda: set_chapter_status(
            project_name,
            arguments["chapter_number"],
            arguments["status"],
        ),
        "update_chapter_info": lambda: update_chapter_info(
            project_name,
            arguments["chapter_number"],
            arguments.get("title", ""),
            arguments.get("summary", ""),
            arguments.get("notes", ""),
            arguments.get("word_count_target", 0),
        ),
        "add_volume": lambda: add_volume_tool(
            project_name,
            arguments["title"],
            arguments.get("part_id", ""),
            arguments.get("summary", ""),
            arguments.get("theme", ""),
        ),
        "delete_volume": lambda: delete_volume_tool(
            project_name,
            arguments["volume_id"],
        ),
        "delete_plot_line": lambda: delete_plot_line_tool(
            project_name,
            arguments["plot_id"],
        ),
        "delete_character": lambda: delete_character_tool(
            project_name,
            arguments["char_id"],
        ),
        "delete_scene": lambda: delete_scene_tool(
            project_name,
            arguments["chapter_number"],
            arguments["scene_index"],
        ),
        # 跨模式工具（预分派在 core.py 处理，不会到这里，但保留映射以防回退）
        "switch_mode": lambda: f"[Internal] switch_mode is handled by AgentLoop pre-dispatch",
        # 持久记忆工具
        "save_agent_memory": lambda: save_agent_memory(
            project_name,
            arguments["key"],
            arguments["value"],
        ),
        "get_agent_memory": lambda: get_agent_memory(
            project_name,
            arguments.get("key", ""),
        ),
        # 新增工具：剧情线、故事信息、角色关系、自定义文档
        "add_plot_line": lambda: _add_plot_line(project_name, arguments),
        "update_story_info": lambda: _update_story_info(project_name, arguments),
        "add_character_relationship": lambda: _add_character_relationship(project_name, arguments),
        "add_custom_document": lambda: _add_custom_document(project_name, arguments),
        "get_custom_document": lambda: _get_custom_document(project_name, arguments),
        "list_custom_documents": lambda: _list_custom_documents(project_name, arguments),
        "update_custom_document": lambda: _update_custom_document(project_name, arguments),
        "delete_custom_document": lambda: _delete_custom_document(project_name, arguments),
    }

    func = tool_map.get(tool_name)
    if not func:
        return f"[Error] Unknown tool: {tool_name}"

    try:
        result = func()
        # 格式化输出
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)
    except Exception as e:
        return f"[Tool Error] {tool_name}: {e}"


def _add_chapter(project_name: str, args: dict) -> dict:
    """内部：添加章节"""
    import os
    from pathlib import Path
    from wal.core import StoryManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    sm = StoryManager(proj_path)
    sm.load_story()
    ch = sm.add_chapter(
        title=args["title"],
        summary=args.get("summary", ""),
        word_count_target=args.get("word_count_target", 3000),
        volume_id=args.get("volume_id", ""),
        volume_number=args.get("volume_number", 0),
        chapter_number=args.get("chapter_number", 0),
    )
    return {"number": ch.number, "title": ch.title, "status": ch.status}


def _add_character(project_name: str, args: dict) -> dict:
    """内部：添加角色"""
    import os
    from pathlib import Path
    from wal.core import CharacterManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    cm = CharacterManager(proj_path)
    cm.load()

    traits = args.get("personality_traits", "")
    traits_list = [t.strip() for t in traits.split(",") if t.strip()] if traits else []

    c = cm.create_character(
        name=args["name"],
        role=args.get("role", "supporting"),
        background_story=args.get("background_story", ""),
        motivation=args.get("motivation", ""),
        personality_traits=traits_list,
    )
    return {"id": c.id, "name": c.name, "role": c.role}


def _add_plot_line(project_name: str, args: dict) -> dict:
    """内部：创建剧情线"""
    import os
    from pathlib import Path
    from wal.core import PlotManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    pm = PlotManager(proj_path)
    pm.load()
    pl = pm.create_plot_line(
        name=args["name"],
        plot_type=args.get("plot_type", "sub"),
        description=args.get("description", ""),
        theme=args.get("theme", ""),
        started_in_chapter=args.get("started_in_chapter", 1),
        target_chapter=args.get("target_chapter", 0),
        level=args.get("level", ""),
        parent_id=args.get("parent_id", ""),
    )
    return {
        "id": pl.id, "name": pl.name,
        "plot_type": pl.plot_type.value if hasattr(pl.plot_type, 'value') else str(pl.plot_type),
        "level": pl.level.value if hasattr(pl.level, 'value') else str(pl.level),
        "status": pl.status.value if hasattr(pl.status, 'value') else str(pl.status),
    }


def _update_story_info(project_name: str, args: dict) -> dict:
    """内部：更新故事信息"""
    import os
    from pathlib import Path
    from wal.core import StoryManager
    from wal.models.story import StoryStatus

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    sm = StoryManager(proj_path)
    sm.load_story()

    updates = {}
    for key in ("name", "author", "summary", "genre", "notes"):
        val = args.get(key, "")
        if val:
            updates[key] = val

    # status 需转为 StoryStatus 枚举
    status_str = args.get("status", "")
    if status_str:
        status_map = {
            "planning": StoryStatus.PLANNING,
            "writing": StoryStatus.WRITING,
            "completed": StoryStatus.COMPLETED,
            "paused": StoryStatus.PAUSED,
            "done": StoryStatus.COMPLETED,  # alias
        }
        if status_str in status_map:
            updates["status"] = status_map[status_str]

    tags_str = args.get("tags", "")
    if tags_str:
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        updates["tags"] = tags_list

    if updates:
        sm.update_story(**updates)

    story = sm.get_story()
    return {
        "name": story.name,
        "author": story.author,
        "summary": story.summary,
        "genre": story.genre,
        "tags": story.tags,
        "status": story.status.value if hasattr(story.status, 'value') else str(story.status),
    }


def _add_character_relationship(project_name: str, args: dict) -> dict:
    """内部：添加角色关系"""
    import os
    from pathlib import Path
    from wal.core import CharacterManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    cm = CharacterManager(proj_path)
    cm.load()

    # 支持按名称或ID查找角色
    char_a = _resolve_character_id(cm, args["char_a"])
    char_b = _resolve_character_id(cm, args["char_b"])

    rel = cm.add_relationship(
        char_a=char_a,
        char_b=char_b,
        rel_type=args["rel_type"],
        description=args.get("description", ""),
        dynamics=args.get("dynamics", ""),
        history=args.get("history", ""),
    )
    return {
        "char_a": rel.character_a, "char_b": rel.character_b,
        "rel_type": rel.rel_type.value if hasattr(rel.rel_type, 'value') else str(rel.rel_type),
        "description": rel.description,
    }


def _resolve_character_id(cm, name_or_id: str) -> str:
    """按ID或名称解析角色ID。若传入的是ID（char_xxx格式），直接返回；否则按名称模糊搜索。"""
    # 已是标准ID格式
    if name_or_id.startswith("char_"):
        char = cm.get_character(name_or_id)
        if char:
            return name_or_id
        raise ValueError(f"角色 {name_or_id} 不存在")

    # 按名称搜索
    matches = []
    for cid, char in cm._characters.items():
        if name_or_id in char.name or name_or_id in (char.aliases or []):
            matches.append(cid)
    if len(matches) == 1:
        return matches[0]
    elif len(matches) == 0:
        raise ValueError(f"未找到名为 '{name_or_id}' 的角色，请先用 list_characters 查看或 add_character 创建")
    else:
        raise ValueError(f"找到多个匹配 '{name_or_id}' 的角色：{matches}，请使用角色ID精确指定")


def _add_custom_document(project_name: str, args: dict) -> dict:
    """内部：创建自定义文档"""
    import os, sqlite3, uuid
    from pathlib import Path
    from datetime import datetime

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    doc_id = f"cd_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    tags_str = args.get("tags", "")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    conn.execute(
        """INSERT INTO custom_documents (id, story_id, title, category, content, tags, created_at, updated_at)
           VALUES (?, 'main', ?, ?, ?, ?, ?, ?)""",
        (doc_id, args["title"], args.get("category", ""), args.get("content", ""),
         json.dumps(tags, ensure_ascii=False), now, now),
    )
    conn.commit()
    conn.close()
    return {"doc_id": doc_id, "title": args["title"], "category": args.get("category", "")}


def _get_custom_document(project_name: str, args: dict) -> dict:
    """内部：获取自定义文档"""
    import os, sqlite3
    from pathlib import Path

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT * FROM custom_documents WHERE id = ? AND story_id = 'main'",
        (args["doc_id"],),
    ).fetchone()
    conn.close()

    if not row:
        return {"error": f"文档 {args['doc_id']} 不存在"}
    return {
        "doc_id": row["id"], "title": row["title"], "category": row["category"],
        "content": row["content"], "tags": json.loads(row["tags"]),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _list_custom_documents(project_name: str, args: dict) -> list:
    """内部：列出自定义文档摘要"""
    import os, sqlite3
    from pathlib import Path

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    category = args.get("category", "")
    limit = args.get("limit", 20)

    if category:
        rows = conn.execute(
            "SELECT id, title, category, content, tags, created_at, updated_at "
            "FROM custom_documents WHERE story_id = 'main' AND category = ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, category, content, tags, created_at, updated_at "
            "FROM custom_documents WHERE story_id = 'main' "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()

    results = []
    for row in rows:
        content = row["content"] or ""
        results.append({
            "doc_id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "preview": content[:100] + ("..." if len(content) > 100 else ""),
            "tags": json.loads(row["tags"]),
            "updated_at": row["updated_at"],
        })
    return results


def _update_custom_document(project_name: str, args: dict) -> dict:
    """内部：更新自定义文档"""
    import os, sqlite3
    from pathlib import Path
    from datetime import datetime

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 检查文档存在
    existing = conn.execute(
        "SELECT * FROM custom_documents WHERE id = ? AND story_id = 'main'",
        (args["doc_id"],),
    ).fetchone()
    if not existing:
        conn.close()
        return {"error": f"文档 {args['doc_id']} 不存在"}

    updates = {}
    for key in ("title", "category", "content"):
        val = args.get(key, "")
        if val:
            updates[key] = val

    tags_str = args.get("tags", "")
    if tags_str:
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        updates["tags"] = json.dumps(tags_list, ensure_ascii=False)

    if updates:
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [args["doc_id"]]
        conn.execute(
            f"UPDATE custom_documents SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()

    row = conn.execute(
        "SELECT * FROM custom_documents WHERE id = ?", (args["doc_id"],),
    ).fetchone()
    conn.close()
    return {
        "doc_id": row["id"], "title": row["title"], "category": row["category"],
        "content": row["content"], "tags": json.loads(row["tags"]),
        "updated_at": row["updated_at"],
    }


def _delete_custom_document(project_name: str, args: dict) -> dict:
    """内部：删除自定义文档"""
    import os, sqlite3
    from pathlib import Path

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))

    conn.execute(
        "DELETE FROM custom_documents WHERE id = ? AND story_id = 'main'",
        (args["doc_id"],),
    )
    deleted = conn.total_changes > 0
    conn.commit()
    conn.close()

    if deleted:
        return {"deleted": True, "doc_id": args["doc_id"]}
    return {"error": f"文档 {args['doc_id']} 不存在"}
