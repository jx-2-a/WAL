"""TOOL_DEFINITIONS — writing tool JSON schemas"""

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
            "description": "向故事添加新章节。建议根据章节在故事中的位置指定合适的 word_count_target：高潮章节 4000-6000，常规章节 2500-4000，过渡/间章 1500-2500。不指定章节号则自动追加到末尾。",
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
                        "description": "目标字数。默认 3000，但应根据章节类型灵活设定：高潮章 4000-6000，常规章 2500-4000，过渡/间章 1500-2500。叙事完整性优先，不必死守数字",
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
            "name": "update_character",
            "description": "更新角色档案。用于角色成长、性格变化、外貌改变、动机转变等。所有参数可选，只传要更新的字段即可。",
            "parameters": {
                "type": "object",
                "properties": {
                    "char_id": {
                        "type": "string",
                        "description": "角色ID（如 char_001）或角色名",
                    },
                    "personality_traits": {
                        "type": "string",
                        "description": "新的性格特征（逗号分隔），如 '勇敢,多疑,坚韧'。覆盖原有特征。",
                    },
                    "motivation": {
                        "type": "string",
                        "description": "新的核心动机",
                    },
                    "appearance": {
                        "type": "string",
                        "description": "新的外貌描述",
                    },
                    "age": {
                        "type": "string",
                        "description": "新的年龄（可为范围或描述）",
                    },
                    "background_story": {
                        "type": "string",
                        "description": "补充的背景故事",
                    },
                    "arc_progress": {
                        "type": "string",
                        "description": "弧光进度描述（如 '弧光中期：从孤僻走向信任'）",
                    },
                    "notes": {
                        "type": "string",
                        "description": "备注（如更新的原因）",
                    },
                },
                "required": ["char_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_chapter_artifacts",
            "description": "查看指定章节关联的所有状态数据（角色快照、情节点、伏笔引用、场景数）。重写某章前先用此工具检查哪些状态会被删除操作级联清理，确保重写后重新记录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "要检查的章节号",
                    },
                },
                "required": ["chapter_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_volume",
            "description": "更新卷信息：标题、摘要、主题、状态(planning/writing/completed)、备注。所有参数可选，只传要更新的字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_id": {
                        "type": "string",
                        "description": "卷ID（如 vol_001）",
                    },
                    "title": {
                        "type": "string",
                        "description": "新的卷标题",
                    },
                    "summary": {
                        "type": "string",
                        "description": "新的卷摘要",
                    },
                    "theme": {
                        "type": "string",
                        "description": "新的卷主题",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["planning", "writing", "completed"],
                        "description": "新状态",
                    },
                    "notes": {
                        "type": "string",
                        "description": "备注",
                    },
                },
                "required": ["volume_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_plot_line",
            "description": "更新剧情线属性：名称、描述、主题、状态(active/completed/abandoned)、计划收束章节。所有参数可选，只传要更新的字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_id": {
                        "type": "string",
                        "description": "剧情线ID（如 plot_001）",
                    },
                    "name": {
                        "type": "string",
                        "description": "新的剧情线名称",
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述",
                    },
                    "theme": {
                        "type": "string",
                        "description": "新的主题",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "abandoned"],
                        "description": "新状态",
                    },
                    "target_chapter": {
                        "type": "integer",
                        "description": "计划收束章节号",
                    },
                },
                "required": ["plot_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_foreshadowing",
            "description": "更新伏笔属性：描述、紧急度(low/medium/high/critical)、计划回收章节、回收说明。不修改状态和埋设章节（用 resolve_foreshadowing 回收）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "fw_id": {
                        "type": "string",
                        "description": "伏笔ID（如 fw_001）",
                    },
                    "description": {
                        "type": "string",
                        "description": "新的伏笔描述",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "紧急程度",
                    },
                    "target_chapter": {
                        "type": "integer",
                        "description": "计划回收章节号",
                    },
                    "resolution_notes": {
                        "type": "string",
                        "description": "回收说明/备注",
                    },
                },
                "required": ["fw_id"],
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
            "name": "set_temperature",
            "description": "设置或查看 LLM 模型的随机性/创造性（temperature）。范围 0.0 ~ 2.0，默认 0.7。值越高回复越有创意和多样性，值越低回复越确定和一致。不传参数则查看当前值。适合场景：需要严谨逻辑时降低（如 0.1~0.3），需要创意灵感时提高（如 1.0~1.5）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "temperature": {
                        "type": "number",
                        "description": "temperature 值，范围 0.0 ~ 2.0。不传则查看当前 temperature。",
                    },
                },
                "required": [],
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
                    "style": {
                        "type": "string",
                        "description": "写作风格指令，如「文风简洁有力，多用短句」「轻松幽默」「严肃沉重」。设定后 AI 将遵循此风格写作",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_writing_style",
            "description": "设置或查看写作风格。传入 style 参数时更新写作风格；不传参数时返回当前写作风格。设定后 AI 在所有模式下的写作都会遵循此风格指令。",
            "parameters": {
                "type": "object",
                "properties": {
                    "style": {
                        "type": "string",
                        "description": "写作风格指令，如「文风简洁有力，多用短句」「轻松幽默的日常文风」「严肃沉重，多用长句刻画心理」。留空则仅查看当前风格。",
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
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定路径的文件内容（仅限文本文件）。可以读取项目目录下的参考文档、笔记、配置文件等。支持指定起始行和读取行数限制。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件的绝对路径或相对于当前工作目录的路径",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码，默认 utf-8。可指定 gbk、gb2312 等",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "从第几行开始读取（行号从1开始），默认从第1行开始",
                    },
                    "line_limit": {
                        "type": "integer",
                        "description": "最多读取多少行，默认读取全部。对大文件建议设置此参数",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_writing_mandate",
            "description": "【防跑偏核心】获取写作指令：当前卷+章节范围锁+铁律+骨架锚点+必读设定文档。自主模式写正文前必须先调用（系统提示词已自动注入一份，主动调用可获得完整版并确认当前卷）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "指定卷号（可选，0=自动定位当前卷）",
                    },
                    "current_chapter": {
                        "type": "integer",
                        "description": "指定当前章（可选，用于提取本章锚点）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_current_volume",
            "description": "【防跑偏核心】声明当前写作卷，建立范围锁。写章超出当前卷范围时需显式调用本工具确认进入下一卷才能继续。",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "卷号，如 3",
                    },
                },
                "required": ["volume_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume_range",
            "description": "声明卷的章节范围（范围锁）。例：卷三=50~72 → set_volume_range(3, 50, 72)。声明后 add_chapter 会自动按范围挂卷，越界写章会被警告。",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "卷号",
                    },
                    "start_chapter": {
                        "type": "integer",
                        "description": "卷的起始章节号",
                    },
                    "end_chapter": {
                        "type": "integer",
                        "description": "卷的结束章节号",
                    },
                },
                "required": ["volume_number", "start_chapter", "end_chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_volume_ranges",
            "description": "列出所有卷及其章节范围锁。",
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
            "name": "add_iron_law",
            "description": "【防跑偏核心】新增铁律：设定剧情红线关键词及其允许/禁止卷。写正文时命中且落在禁止范围即报违规。例：万山之祖传承只在卷五 → add_iron_law(name='万山之祖传承', keywords=['万山之祖','传承','接替'], only_in_volume=5)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "铁律名称",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键词列表，正文命中即触发扫描",
                    },
                    "forbidden_volumes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "禁止出现这些关键词的卷号列表",
                    },
                    "only_in_volume": {
                        "type": "integer",
                        "description": "关键词只允许出现的卷号（0=不限）",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["warning", "block"],
                        "description": "违规严重度：warning=警告 / block=拦截",
                    },
                    "note": {
                        "type": "string",
                        "description": "铁律说明",
                    },
                },
                "required": ["name", "keywords"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_iron_laws",
            "description": "列出全部铁律。",
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
            "name": "delete_iron_law",
            "description": "删除一条铁律。",
            "parameters": {
                "type": "object",
                "properties": {
                    "law_id": {
                        "type": "string",
                        "description": "铁律ID，如 law_001",
                    },
                },
                "required": ["law_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_iron_law",
            "description": "扫描指定章节正文是否命中铁律违规（写后自查/写前检查）。",
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
            "name": "set_chapter_anchor",
            "description": "设置章节锚点（本章应写什么）。check_chapter_alignment 的对照依据；可把骨架文档中该章的规划内容设为锚点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "anchor": {
                        "type": "string",
                        "description": "锚点内容，如「孤霞岭：青见继承万山之祖传承的伏笔揭晓」",
                    },
                },
                "required": ["chapter_number", "anchor"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_auto_mandatory_docs",
            "description": "配置自主模式启动必读文档（按顺序注入写作指令）。传入自定义文档ID列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "自定义文档ID列表，如 ['cd_bb59afe6', 'cd_13d531c8']",
                    },
                },
                "required": ["doc_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_chapter",
            "description": "移动章节：把章节改到新章节号，级联迁移所有引用（场景/全文索引/角色快照/情节点/伏笔）。目标号被占用会报错。",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_number": {
                        "type": "integer",
                        "description": "原章节号",
                    },
                    "to_number": {
                        "type": "integer",
                        "description": "新章节号",
                    },
                },
                "required": ["from_number", "to_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "renumber_chapters",
            "description": "批量重排章节号：从 start_at 起的章节顺延为 new_start 起。删除中间章节留下空洞时使用（如删了第5章，把6..N前移：renumber_chapters(6, 5)）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_at": {
                        "type": "integer",
                        "description": "从此章节号开始重排，默认1",
                    },
                    "new_start": {
                        "type": "integer",
                        "description": "重排后的起始号，默认1",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_chapter_to_volume",
            "description": "把指定章节挂到指定卷下（写 chapters.volume_id）。用于修复历史遗留的未挂卷章节。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "volume_number": {
                        "type": "integer",
                        "description": "目标卷号",
                    },
                },
                "required": ["chapter_number", "volume_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_chapters_to_volume",
            "description": "批量把 start~end 章挂到指定卷。一次修完历史遗留的未挂卷章节。",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "目标卷号",
                    },
                    "start": {
                        "type": "integer",
                        "description": "起始章节号",
                    },
                    "end": {
                        "type": "integer",
                        "description": "结束章节号",
                    },
                },
                "required": ["volume_number", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_plot_point",
            "description": "向剧情线添加情节点，可绑定到指定章节（chapter_assigned）。绑定后 set_chapter_status(done) 会自动推进。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_id": {
                        "type": "string",
                        "description": "剧情线ID，如 plot_001",
                    },
                    "title": {
                        "type": "string",
                        "description": "情节点标题",
                    },
                    "chapter_assigned": {
                        "type": "integer",
                        "description": "绑定到的章节号（可选，0=未绑定）",
                    },
                    "description": {
                        "type": "string",
                        "description": "情节点描述",
                    },
                    "emotional_tone": {
                        "type": "string",
                        "description": "情绪基调",
                    },
                    "impacts_characters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "影响到的角色ID",
                    },
                    "estimated_words": {
                        "type": "integer",
                        "description": "预计字数",
                    },
                },
                "required": ["plot_id", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_plot_point_to_chapter",
            "description": "把情节点绑定到指定章节（进度绑定）。章节完成后自动推进该情节点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_id": {
                        "type": "string",
                        "description": "剧情线ID",
                    },
                    "point_id": {
                        "type": "string",
                        "description": "情节点ID",
                    },
                    "chapter": {
                        "type": "integer",
                        "description": "章节号",
                    },
                },
                "required": ["plot_id", "point_id", "chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bind_plot_points_to_chapter",
            "description": "批量把剧情线的多个情节点绑定到指定章节。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_id": {
                        "type": "string",
                        "description": "剧情线ID",
                    },
                    "chapter": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "point_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "情节点ID列表",
                    },
                },
                "required": ["plot_id", "chapter", "point_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_advance_plot",
            "description": "章节完成后自动推进：把绑定到该章的情节点标记为完成，剧情线进度自动上涨。set_chapter_status(done) 时系统会自动调用。",
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
            "name": "check_chapter_alignment",
            "description": "写后对照：本章实际内容 vs 锚点（规划）。关键词级匹配——按锚点逐字覆盖命中率判定对齐（覆盖率≥40% 且≥2个关键词命中即对齐，容忍近义改写/刻意省略的人名地名），输出命中/缺失清单。",
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
            "name": "global_replace",
            "description": "全书查找替换：改设定/人名时不用一章章翻。默认只替换场景正文，可选替换章节标题/摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "old": {
                        "type": "string",
                        "description": "要替换的原文",
                    },
                    "new": {
                        "type": "string",
                        "description": "替换为",
                    },
                    "in_titles": {
                        "type": "boolean",
                        "description": "是否同时替换章节标题",
                    },
                    "in_summaries": {
                        "type": "boolean",
                        "description": "是否同时替换章节摘要",
                    },
                },
                "required": ["old", "new"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "merge_scenes",
            "description": "合并章内两个场景：内容并入 scene_a，删除 scene_b，重排索引。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "scene_a": {
                        "type": "integer",
                        "description": "保留的场景索引",
                    },
                    "scene_b": {
                        "type": "integer",
                        "description": "被合并删除的场景索引",
                    },
                },
                "required": ["chapter", "scene_a", "scene_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "split_scene",
            "description": "按字符位置拆分场景为两个场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "scene_index": {
                        "type": "integer",
                        "description": "要拆分的场景索引",
                    },
                    "split_at": {
                        "type": "integer",
                        "description": "拆分字符位置（0~正文长度之间）",
                    },
                },
                "required": ["chapter", "scene_index", "split_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "story_timeline",
            "description": "故事内时间轴：各章场景的时间点 + timeline_events 表。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]
