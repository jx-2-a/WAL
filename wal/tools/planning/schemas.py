"""PLAN_TOOL_DEFINITIONS — planning tool JSON schemas"""

PLAN_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "suggest_plot_direction",
            "description": "基于当前剧情状态分析，建议剧情发展方向。返回主线/支线进度、伏笔状态、角色概况，供 Agent 讨论可能的下一步方向。",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "额外的上下文/关注点，如「主角刚突破修为，需要新的挑战」",
                    },
                    "count": {
                        "type": "integer",
                        "description": "建议方向的数量，默认3",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brainstorm_character_arc",
            "description": "为指定角色构思弧光发展方向。分析角色当前状态、演变历程和关系网，提供成长/堕落/救赎/觉醒等弧光方向参考。",
            "parameters": {
                "type": "object",
                "properties": {
                    "char_id": {
                        "type": "string",
                        "description": "角色ID，如 char_001",
                    },
                    "char_name": {
                        "type": "string",
                        "description": "角色名称（如果不知道ID也可以按名称搜索）",
                    },
                    "focus": {
                        "type": "string",
                        "description": "关注的弧光方向，如「成长」「堕落」「救赎」",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_plot_holes",
            "description": "分析剧情漏洞和逻辑不一致。检查：未收束支线、伏笔回收状态、角色一致性、时间线冲突、角色长期缺席等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "deep": {
                        "type": "boolean",
                        "description": "是否启用深度分析（包括逐章时间线检查等），默认 false",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_plot_twist",
            "description": "基于当前剧情状态，构思剧情转折。支持类型：身份揭露、背叛、牺牲、意外盟友、隐藏敌人、力量格局变化、道德困境。",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "转折的上下文/限制条件，如「需要在第20章左右」「不能涉及主角死亡」",
                    },
                    "twist_type": {
                        "type": "string",
                        "enum": ["revelation", "betrayal", "sacrifice", "unexpected_ally", "hidden_enemy", "power_shift", "moral_dilemma"],
                        "description": "转折类型（可选，不填则给出全部类型建议）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_pacing",
            "description": "评估故事节奏。分析章节字数分布、波动性、情节推进速度、高潮/过渡比例，给出节奏调整建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_chapter": {
                        "type": "integer",
                        "description": "评估起始章节（默认从第1章开始）",
                    },
                    "end_chapter": {
                        "type": "integer",
                        "description": "评估结束章节（默认到最后一章）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_conflict_escalation",
            "description": "建议冲突升级方案。分析当前冲突关系、对抗格局，给出升级路径建议。覆盖角色冲突、社会冲突、内在冲突、命运冲突等维度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "conflict_type": {
                        "type": "string",
                        "enum": ["character_vs_character", "character_vs_society", "character_vs_nature", "character_vs_self", "character_vs_fate", "character_vs_technology"],
                        "description": "关注的冲突类型（可选，默认分析全部）",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "在当前章节号的背景下分析冲突升级（可选）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brainstorm_world_building",
            "description": "构思世界观扩展方向。分析当前世界设定的完整度，建议：地理扩展、历史神话、社会结构、魔法/科技体系、种族文明、经济贸易等方向的扩展。",
            "parameters": {
                "type": "object",
                "properties": {
                    "aspect": {
                        "type": "string",
                        "enum": ["geography", "history", "society", "magic_tech", "races", "economy", "religion", "ecology"],
                        "description": "关注的扩展方向（可选，默认分析全部）",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "在当前章节背景下分析（可选）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_theme_consistency",
            "description": "分析主题一致性。检查各卷/章节是否围绕核心主题、角色弧光是否与主题呼应、是否有偏离主题的支线、象征/意象使用是否一致。",
            "parameters": {
                "type": "object",
                "properties": {
                    "theme": {
                        "type": "string",
                        "description": "要检查的核心主题词，如「自由」「复仇」「成长」「救赎」。留空则使用故事设定主题。",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_planning_note",
            "description": "保存一条规划分析笔记到数据库。分析完成后务必调用此工具持久化结论，避免对话压缩后分析丢失。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "笔记标题，如「第3卷节奏分析」「角色弧光检查结果」",
                    },
                    "category": {
                        "type": "string",
                        "description": "分类标签：plot/character/world/pacing/theme/general",
                    },
                    "content": {
                        "type": "string",
                        "description": "分析正文（详细的分析过程和发现）",
                    },
                    "decisions": {
                        "type": "string",
                        "description": "基于分析做出的决策/结论",
                    },
                    "related_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "使用了哪些分析工具",
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_planning_notes",
            "description": "列出已保存的规划笔记摘要（标题+分类+前150字）。用于回顾之前的分析结论。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "按分类过滤（可选）",
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
            "name": "get_planning_note",
            "description": "获取一条规划笔记的完整内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "笔记ID，如 pn_a1b2c3d4",
                    },
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_mode",
            "description": "切换 Agent 工作模式。规划完成后用此工具切换到 writing 模式执行写作，需要分析时切回 planning。",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["writing", "planning", "autonomous"],
                        "description": "目标模式。规划完成后通常切到 writing",
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
            "description": "保存一条持久记忆（key-value）。记录重要的讨论结论、用户偏好等，重启后仍存在。",
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
