# WAL — 小说写作 AI Agent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-purple)](https://platform.deepseek.com/)
[![SQLite](https://img.shields.io/badge/storage-SQLite%203-green)](https://www.sqlite.org/)

WAL (Writing Assistant Library) 是一个面向百万字级长篇网文的 AI 写作助手。终端交互式 Agent，调用 DeepSeek API，自动管理剧情结构、追踪角色弧光、推进写作流程。

## 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

### 2. 配置 API Key

```powershell
copy .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

> 获取: https://platform.deepseek.com/api_keys

### 3. 启动

```powershell
.\start.ps1                # 交互选择项目
.\start.ps1 项目名          # 直接打开
.\start.ps1 项目名 -Quiet  # 安静模式（隐藏工具调用）
```

---

## 三种工作模式

| 模式 | 切换 | 工具数 | 用途 |
|------|------|--------|------|
| **[Write] 写作** | `/w`（默认） | 44 | 内容创作、管理、搜索、导出 |
| **[Plan] 规划** | `/p` | 14 | 创意讨论、剧情分析（只读） |
| **[Auto] 自主** | `/a` | 54 | 批量自动写作 + 检查点保护 |

自主模式下：Agent 连续循环推进，轮间按 **Enter** 暂停说话，`/sa` 退出。

---

## Agent 工具一览

### 写作模式 (44 个)

**故事管理 (10)**
`get_story_status` `get_chapter_context` `get_chapter_context_text` `get_volume_context` `list_volumes` `add_chapter` `delete_chapter` `set_chapter_status` `update_chapter_info` `add_volume`

**场景写作 (3)**
`write_scene_content` `suggest_next_scene` `delete_scene`

**剧情管理 (9)**
`list_plot_lines` `get_plot_tree` `plot_health_check` `list_dangling_plots` `add_plot_line` `update_plot_point` `add_foreshadowing` `resolve_foreshadowing` `check_foreshadowing_health`

**角色管理 (7)**
`list_characters` `get_character` `add_character` `add_character_relationship` `character_relationship_map` `create_character_snapshot` `get_character_evolution`

**全文搜索 (3)**
`search_story_index` `quick_review` `generate_chapter_summary`

**导出 (3)**
`export_novel_files` — 支持 plain/markdown/html/**docx**，支持 volume/chapter/**single** 分层，**structure=flat** 纯章节模式

`export_outline` `export_yaml_backup`

**世界观 (2)**
`get_world_setting` `brainstorm_world_building_agent`

**自定义文档 (5)**
`add_custom_document` `get_custom_document` `list_custom_documents` `update_custom_document` `delete_custom_document`

**跨模式 (3)**
`switch_mode` `save_agent_memory` `get_agent_memory`

**故事信息 (2)**
`update_story_info` `suggest_plot_direction`

### 规划模式 (14 个)

8 个分析工具 + 3 个持久化工具 + 3 个跨模式工具

| 工具 | 用途 |
|------|------|
| `suggest_plot_direction` | 分析剧情现状，建议发展方向 |
| `brainstorm_character_arc` | 为角色构思弧光 |
| `analyze_plot_holes` | 检测剧情漏洞 |
| `propose_plot_twist` | 构思剧情转折 |
| `evaluate_pacing` | 评估故事节奏 |
| `suggest_conflict_escalation` | 建议冲突升级 |
| `brainstorm_world_building` | 构思世界观扩展 |
| `analyze_theme_consistency` | 检查主题一致性 |
| `add_planning_note` | 保存分析结论 |
| `list_planning_notes` | 查看规划笔记 |
| `get_planning_note` | 查看完整笔记 |
| `switch_mode` `save_agent_memory` `get_agent_memory` | 跨模式 |

### 自主模式 (54 个)

全部 44 个写作工具 + 13 个自主控制工具（去重后）：

| 工具 | 用途 |
|------|------|
| `set_autonomy_level` | 自主等级 (suggest_only/auto_minor/auto_moderate/full_auto) |
| `set_direction` | 写作方向/目标 |
| `start_auto_session` `end_auto_session` | 会话管理 |
| `create_checkpoint` `rollback_to_checkpoint` `list_checkpoints` | 检查点保护 |
| `approve_decision` `reject_decision` | 决策审批 |
| `get_auto_status` | 状态 + 待审批列表 |
| `switch_mode` `save_agent_memory` `get_agent_memory` | 跨模式 |

---

## CLI 管理命令

```powershell
$env:PYTHONPATH = "."; $py = "d:\PyVenv\WAL\Scripts\python.exe"

# 项目
& $py -m wal.cli.main init <名> --author <作者> --summary <简介> --genre <类型>
& $py -m wal.cli.main status <名>
& $py -m wal.cli.main outline <名>

# 章节/卷/部
& $py -m wal.cli.main chapter-add <名> "标题" --words 3000 --volume 1
& $py -m wal.cli.main volume-add <名> "标题" --theme "主题"
& $py -m wal.cli.main volume-list <名>
& $py -m wal.cli.main part-add <名> "部标题"

# 剧情
& $py -m wal.cli.main plot-list <名>
& $py -m wal.cli.main plot-add <名> "剧情名" --type main
& $py -m wal.cli.main plot-point-add <名> <plot_id> "情节点" --chapter 1
& $py -m wal.cli.main plot-check <名>
& $py -m wal.cli.main plot-tree <名>

# 角色
& $py -m wal.cli.main char-list <名>
& $py -m wal.cli.main char-add <名> "角色" --role protagonist
& $py -m wal.cli.main char-check <名>

# 搜索
& $py -m wal.cli.main index-search <名> "关键词"
& $py -m wal.cli.main review <名> 1 20 --topic "叶凡"

# 导出
& $py -m wal.cli.main export <名> --to-files                          # 按卷分文件
& $py -m wal.cli.main export <名> --to-files --split single --format docx      # 单文件总集 DOCX
& $py -m wal.cli.main export <名> --to-files --split single --structure flat   # 纯章节总集
& $py -m wal.cli.main export <名> --full --format docx                 # 全书 DOCX
```

---

## 导出选项

| 选项 | 值 | 说明 |
|------|-----|------|
| `--format` | plain / markdown / html / **docx** | docx 自带中文排版（微软雅黑 12pt，首行缩进） |
| `--split` | volume / chapter / **single** / auto | single=全书合并为单文件（总集） |
| `--structure` | full / **flat** | flat=纯章节排列，无卷标题（仅 single 模式） |

---

## 项目结构

```
WAL/
├── start.ps1                  # 一键启动
├── .env.example               # API Key 模板
├── requirements.txt
├── wal/                       # Python 主包
│   ├── agent/
│   │   ├── core.py            # AgentLoop — 核心循环（UI 无关）
│   │   ├── repl.py            # TerminalREPL — Rich 终端界面
│   │   ├── launch.py          # 启动入口
│   │   ├── tools.py           # 44 个写作工具
│   │   ├── tool_defs.py       # 工具定义 + 执行调度
│   │   ├── plan_mode.py       # 模式枚举 + 系统提示词
│   │   ├── plan_tools.py      # 8 个规划工具
│   │   ├── plan_tool_defs.py  # 规划工具定义
│   │   ├── auto_tools.py      # 13 个自主控制工具
│   │   ├── auto_tool_defs.py  # 自主工具定义
│   │   ├── memory_tools.py    # Agent 持久记忆
│   │   └── SKILL.md
│   ├── engine/
│   │   ├── llm_client.py      # DeepSeek API（OpenAI 兼容）
│   │   ├── context_manager.py # 滑动窗口 + 摘要压缩 + RAG
│   │   ├── context_builder.py # 写作上下文组装
│   │   └── prompt_builder.py  # Jinja2 模板
│   ├── core/
│   │   ├── story_manager.py   # 故事/卷/章 CRUD + 导出（含 DOCX）
│   │   ├── plot_manager.py    # 剧情线/情节点/伏笔
│   │   ├── char_manager.py    # 角色/关系/快照
│   │   ├── world_manager.py   # 世界观/地点/时间线
│   │   ├── index_manager.py   # FTS5 搜索/里程碑
│   │   └── auto_manager.py    # 检查点/决策/自主等级
│   ├── models/                # Pydantic 数据模型（5 组）
│   ├── storage/               # SQLite 持久化（17 表 + FTS5）
│   │   ├── database.py        # Schema DDL + 迁移
│   │   ├── story_repo.py      # 7 个 Repository
│   │   ├── ...
│   │   └── migrate.py         # YAML → SQLite 迁移
│   └── cli/main.py            # 26 个 CLI 命令
├── projects/                  # 用户项目（不入库）
└── Dur/                       # 测试
```

---

## 架构

```
┌─────────────────────────────┐
│  表现层（可替换）              │
│  TerminalREPL (Rich)         │
└──────────┬──────────────────┘
           │ 回调: on_thinking, on_tool_call, on_response, on_mode_switch
┌──────────▼──────────────────┐
│  AgentLoop (core.py)        │
│  - 对话历史 + 工具调用循环     │
│  - 三种模式 (Write/Plan/Auto) │
│  - 安静模式                   │
│  - ContextManager (窗口+RAG)  │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│  LLMClient (DeepSeek API)   │
│  - Function Calling          │
│  - 流式输出                   │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│  44+14+54 个 Agent Tools     │
│  → Core Managers → SQLite   │
└─────────────────────────────┘
```

---

## 关键设计

- **SQLite 3**: 单文件 `wal.db`，17 表 + FTS5 全文搜索
- **上下文保护**: 滑动窗口 + 摘要压缩 + 结果截断 + RAG 检索注入
- **数据安全**: 检查点备份、回滚前自动备份
- **持久记忆**: `save_agent_memory` / `get_agent_memory`，重启不丢失

## 许可

MIT
