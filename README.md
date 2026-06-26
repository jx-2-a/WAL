# WAL — 小说写作 AI Agent

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-purple)](https://platform.deepseek.com/)
[![SQLite](https://img.shields.io/badge/storage-SQLite%203-green)](https://www.sqlite.org/)
[![Phase](https://img.shields.io/badge/phases-9%2F9%20complete-brightgreen)]()

WAL (Writing Assistant Library) 是一个面向百万字级长篇网文的 AI 写作助手。通过终端交互界面，调用 DeepSeek API，帮助作者管理复杂的剧情结构、追踪角色弧光、自动推进写作流程。

## 快速开始 — 三步启动

### 1. 配置 API Key

```powershell
# 复制模板
copy .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-your-key-here
```

或设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "sk-your-key-here"
```

> 获取 Key: https://platform.deepseek.com/api_keys

### 2. 创建小说项目（首次）

```powershell
d:\PyVenv\WAL\Scripts\python.exe -m wal.cli.main init 修仙传奇 --author "作者名" --summary "故事梗概" --genre "仙侠玄幻"
```

或使用示例项目体验：

```powershell
d:\PyVenv\WAL\Scripts\python.exe Dur\create_example.py
```

### 3. 启动交互式 Agent

```powershell
# 交互选择项目
.\start.ps1

# 直接打开指定项目
.\start.ps1 修仙传奇

# 指定模型
.\start.ps1 修仙传奇 -Model deepseek-reasoner

# 安静模式启动（不显示工具调用详情）
.\start.ps1 修仙传奇 -Quiet

# 以规划模式启动（创意讨论、分析构思）
.\start.ps1 修仙传奇 -Mode planning

# 以自主模式启动（批量自动写作）
.\start.ps1 修仙传奇 -Mode autonomous -Quiet
```

---

## 三种工作模式

WAL 支持三种 Agent 工作模式，通过 `/` 命令随时切换：

| 模式 | 启动命令 | 切换命令 | 工具数 | 用途 |
|------|---------|---------|--------|------|
| **[Write] 写作模式** | 默认 | `/write` / `/w` | 25 个 | 内容产出、管理操作 — 写作、添加角色、管理剧情线、全文搜索、导出 |
| **[Plan] 规划模式** | `-Mode planning` | `/plan` / `/p` | 8 个 | 创意讨论、剧情分析、世界观构思 — 只读分析，不修改数据 |
| **[Auto] 自主模式** | `-Mode autonomous` | `/auto` / `/a` | 35 个 | 批量自主写作 — 全量工具 + 检查点保护 + 决策审批 |

退出自主模式：`/stop-auto` / `/sa`（回到写作模式）

---

## REPL 交互命令

| 命令 | 简写 | 说明 |
|------|------|------|
| `exit` / `quit` / `退出` | — | 退出 Agent |
| `/clear` | `清空` | 清空对话历史 |
| `/help` | `帮助` | 显示当前模式的帮助（含工具列表） |
| `/plan` | `/p` | 切换到规划模式 |
| `/write` | `/w` | 切换到写作模式 |
| `/auto` | `/a` | 切换到自主模式 |
| `/stop-auto` | `/sa` | 退出自主模式，回到写作模式 |
| `/quiet` | `/q` | 开启安静模式（隐藏工具调用详情） |
| `/verbose` | `/v` | 恢复详细模式（显示工具调用） |

### 对话示例

```
[WRITING] You > 帮我看看目前的剧情进度

Agent > 调用 get_story_status, list_plot_lines, list_dangling_plots
       《修仙传奇》已完成 12/45 章，总字数 42,000。
       5 条剧情线：主线 1 条 (33%)，支线 4 条。3 条支线未收束。

[WRITING] You > 第13章该怎么写？给我写作上下文

Agent > 调用 get_chapter_context_text(13), check_foreshadowing_health(13)
       前一章摘要 + 本章剧情任务 + 出场角色档案 + 伏笔提醒 + 场景建议

[WRITING] You > 帮我把叶凡突破金丹期的场面写出来

Agent > 生成正文 → write_scene_content 保存 → update_plot_point 更新进度

[WRITING] You > /plan

[Plan] 已切换到 planning 模式

[PLANNING] You > 分析一下目前的剧情漏洞

Agent > 调用 analyze_plot_holes → 输出结构化的漏洞分析报告

[PLANNING] You > /write

[Write] 已切换到 writing 模式
```

---

## Agent 工具一览

### 写作模式工具 (25 个)

**故事管理**
| 工具 | 用途 |
|------|------|
| `get_story_status` | 查看故事进度（章节数、完成度、字数） |
| `get_chapter_context` | 获取某章的完整写作上下文 |
| `get_volume_context` | 获取卷级写作上下文 |
| `list_volumes` | 列出所有卷及其进度 |
| `add_chapter` | 添加新章节（支持卷编号） |
| `write_scene_content` | 保存场景正文 |
| `suggest_next_scene` | 获取下一场景的写作建议 |
| `export_outline` | 导出故事大纲 |

**剧情管理**
| 工具 | 用途 |
|------|------|
| `list_plot_lines` | 查看所有剧情线进度 |
| `get_plot_tree` | 获取主线/支线/角色弧光的树形结构 |
| `plot_health_check` | 主线支线健康度检查 |
| `list_dangling_plots` | 列出所有未收束支线 |
| `update_plot_point` | 更新情节点状态 |
| `add_foreshadowing` | 添加伏笔 |
| `resolve_foreshadowing` | 收束/回收伏笔 |
| `check_foreshadowing_health` | 伏笔健康检查（超期提醒） |

**角色管理**
| 工具 | 用途 |
|------|------|
| `list_characters` | 列出所有角色 |
| `get_character` | 获取角色完整档案 |
| `character_relationship_map` | 查看角色关系图谱 |
| `add_character` | 添加新角色 |
| `create_character_snapshot` | 按章节创建角色状态快照 |
| `get_character_evolution` | 查看角色弧光演变轨迹 |

**全文搜索**
| 工具 | 用途 |
|------|------|
| `search_story_index` | FTS5 全文搜索（跨章节，毫秒级） |
| `quick_review` | 按章节范围快速回顾 |
| `generate_chapter_summary` | 生成章节结构化摘要 |

**导出**
| 工具 | 用途 |
|------|------|
| `export_chapter` | 导出章节/卷/全书 (markdown/html/plain) |
| `export_yaml_backup` | 导出 YAML 备份（SQLite → YAML 文件） |

### 规划模式工具 (8 个)

| 工具 | 用途 |
|------|------|
| `suggest_plot_direction` | 基于当前状态建议剧情发展方向 |
| `brainstorm_character_arc` | 为指定角色构思人物弧光 |
| `analyze_plot_holes` | 检测剧情漏洞与逻辑矛盾 |
| `propose_plot_twist` | 构思剧情转折方案 |
| `evaluate_pacing` | 评估章节范围的节奏分布 |
| `suggest_conflict_escalation` | 建议冲突升级策略 |
| `brainstorm_world_building` | 构思世界观扩展方向 |
| `analyze_theme_consistency` | 检查主题一致性 |

### 自主模式工具 (10 个)

自主模式拥有全部写作工具 + 以下 10 个自主控制工具：

| 工具 | 用途 |
|------|------|
| `set_autonomy_level` | 设置自主等级 (suggest_only / auto_minor / auto_moderate / full_auto) |
| `set_direction` | 设置自主写作方向/目标 |
| `start_auto_session` | 开始自主写作会话 |
| `end_auto_session` | 结束会话并输出统计 |
| `create_checkpoint` | 创建数据库检查点（wal.db 快照） |
| `rollback_to_checkpoint` | 回滚到指定检查点（自动备份） |
| `list_checkpoints` | 列出所有检查点 |
| `approve_decision` | 审批通过一条决策 |
| `reject_decision` | 拒绝一条决策 |
| `get_auto_status` | 获取自主模式状态 + 待审批决策列表 |

### 自主等级权限

| 等级 | 自动执行 | 需审批 |
|------|----------|--------|
| `suggest_only` | 只读分析/搜索 | 任何修改 |
| `auto_minor` | 状态更新、快照、索引 | moderate+ |
| `auto_moderate` | 场景写入、角色添加 | major+ |
| `full_auto` | 批量写作、剧情推进 | critical only |

---

## start.ps1 参数

```powershell
.\start.ps1 [项目名] [选项]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `-ProjectName` | string | "" | 小说项目名（不填则交互选择） |
| `-Model` | string | deepseek-chat | LLM 模型名称 |
| `-BaseUrl` | string | https://api.deepseek.com/v1 | API 地址 |
| `-Quiet` | switch | false | 以安静模式启动（隐藏工具调用详情） |
| `-Mode` | string | writing | Agent 启动模式：writing / planning / autonomous |
| `-Help` | switch | — | 显示帮助 |

---

## CLI 命令行管理

除了交互式 Agent，也可以通过命令行管理数据：

```powershell
# 设置环境变量
$env:PYTHONPATH = "."

# 项目管理
python -m wal.cli.main init <名称> --author <作者> --summary <简介> --genre <类型>
python -m wal.cli.main status <名称>
python -m wal.cli.main outline <名称>

# 卷/部/章节
python -m wal.cli.main chapter-add <名称> "章节标题" --words 3000 --summary "摘要" --volume 1
python -m wal.cli.main volume-add <名称> "卷标题" --summary "摘要" --theme "主题"
python -m wal.cli.main volume-list <名称>
python -m wal.cli.main part-add <名称> "部标题"

# 剧情
python -m wal.cli.main plot-list <名称>
python -m wal.cli.main plot-add <名称> "剧情名" --type main --desc "描述"
python -m wal.cli.main plot-point-add <名称> <plot_id> "情节点" --chapter 1
python -m wal.cli.main plot-check <名称>
python -m wal.cli.main plot-tree <名称>

# 伏笔
python -m wal.cli.main foreshadowing-add <名称> "伏笔描述" --chapter 3 --target 10 --urgency high
python -m wal.cli.main foreshadowing-list <名称>
python -m wal.cli.main foreshadowing-resolve <名称> <fw_id> --chapter 10

# 角色
python -m wal.cli.main char-list <名称>
python -m wal.cli.main char-add <名称> "角色名" --role protagonist --bg "背景" --motivation "动机"
python -m wal.cli.main char-check <名称>
python -m wal.cli.main char-snapshot <名称> <char_id> --chapter 5 --arc "弧光进展" --changes "变化"

# 索引与搜索
python -m wal.cli.main index-search <名称> "叶凡 AND 突破"
python -m wal.cli.main index-chapter <名称> --chapter 5
python -m wal.cli.main milestone <名称> "第10章完成" --chapter 10
python -m wal.cli.main review <名称> --start 30 --end 40 --topic "叶凡"

# 导出
python -m wal.cli.main export <名称> --chapters 1-5 --format markdown --output ./export/
python -m wal.cli.main write-context <名称> 13
```

---

## 项目结构

```
WAL/
├── start.ps1                 # PowerShell 一键启动脚本
├── .env.example              # API Key 配置模板
├── README.md
├── CLAUDE.md                 # Claude Code 项目指令
├── wal/                      # Python 主包
│   ├── agent/
│   │   ├── core.py           # AgentLoop — 核心逻辑（UI 无关）
│   │   ├── repl.py           # TerminalREPL — Rich 终端界面
│   │   ├── launch.py         # 启动入口（--quiet, --mode）
│   │   ├── tools.py          # 25 个写作工具函数
│   │   ├── tool_defs.py      # 写作工具定义 + 执行调度器
│   │   ├── plan_mode.py      # AgentMode 枚举 + 模式系统提示词
│   │   ├── plan_tools.py     # 8 个规划工具函数
│   │   ├── plan_tool_defs.py # 规划工具定义 + 执行调度器
│   │   ├── auto_tools.py     # 10 个自主工具函数
│   │   ├── auto_tool_defs.py # 自主工具定义 + 执行调度器
│   │   ├── SKILL.md          # Agent 行为指令文档
│   │   └── __init__.py
│   ├── engine/
│   │   ├── llm_client.py     # LLM 客户端（DeepSeek/OpenAI 兼容）
│   │   ├── context_manager.py# 滑动窗口 + 摘要压缩 + RAG 检索
│   │   ├── context_builder.py# 写作上下文组装器
│   │   ├── prompt_builder.py # Jinja2 提示词模板
│   │   └── __init__.py
│   ├── core/
│   │   ├── story_manager.py  # 故事/卷/章节 CRUD + 导出
│   │   ├── plot_manager.py   # 剧情线/情节点/伏笔管理
│   │   ├── char_manager.py   # 角色/关系/快照管理
│   │   ├── world_manager.py  # 世界观/地点/时间线
│   │   ├── index_manager.py  # FTS5 搜索/里程碑/关键词索引
│   │   ├── auto_manager.py   # 检查点/自主等级/决策管理
│   │   └── __init__.py
│   ├── models/
│   │   ├── story.py          # Story, Chapter, Scene, Volume, Part
│   │   ├── character.py      # Character, Relationship, CharacterSnapshot
│   │   ├── plot.py           # PlotLine, PlotPoint, Foreshadowing
│   │   ├── world.py          # Location, WorldSetting, TimelineEvent
│   │   ├── autonomous.py     # AutonomyLevel, AutoDecision, Checkpoint
│   │   └── __init__.py
│   ├── storage/
│   │   ├── database.py       # SQLite 连接 + 架构 (17表 + FTS5) + 迁移/导出
│   │   ├── db_repo.py        # SQLite 通用仓库基类
│   │   ├── story_repo.py     # 故事/卷/章节/场景 Repository
│   │   ├── char_repo.py      # 角色/关系/快照 Repository
│   │   ├── plot_repo.py      # 剧情线/情节点/伏笔 Repository
│   │   ├── world_repo.py     # 世界观/地点/时间线 Repository
│   │   ├── index_repo.py     # FTS5/索引/里程碑 Repository
│   │   ├── auto_repo.py      # 自主决策 + agent_config Repository
│   │   ├── migrate.py        # YAML → SQLite 迁移
│   │   ├── repo.py           # 旧 YAML 仓库基类（保留，用于兼容）
│   │   └── __init__.py
│   └── cli/
│       └── main.py           # 26 个 CLI 命令
├── Dur/                      # 测试 + 示例
│   ├── test_phase6_plan_mode.py
│   ├── test_phase7_auto_mode.py
│   ├── test_phase8_integration.py
│   └── create_example.py
├── projects/                 # 小说项目存储
│   └── <项目名>/
│       ├── wal.db            # SQLite 数据库（主存储）
│       ├── checkpoints/      # 自动检查点备份
│       ├── story.yaml        # YAML 备份（导出/兼容）
│       ├── characters.yaml
│       └── plot_lines.yaml
└── pyproject.toml
```

---

## 架构设计

系统采用核心逻辑与 UI 完全分离的设计：

```
┌──────────────────────────────────────┐
│  表现层（可替换）                      │
│  ├── TerminalREPL  (Rich 终端)        │  ← 当前
│  ├── Web UI        (未来 Flask)       │
│  └── GUI           (未来)             │
└──────────────┬───────────────────────┘
               │ 回调: on_thinking, on_tool_call, on_response, on_mode_switch
┌──────────────▼───────────────────────┐
│  AgentLoop (wal/agent/core.py)       │
│  - 对话历史 + 工具调用循环             │
│  - 三种模式 (Write/Plan/Auto)         │
│  - 安静模式 (抑制工具调用通知)          │
│  - ContextManager (滑动窗口 + RAG)     │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  LLMClient (wal/engine/)             │
│  - OpenAI 兼容协议 (DeepSeek)         │
│  - 流式输出 + Function Calling        │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  43 个 Agent Tools (3 套工具集)       │
│  ├── 25 写作工具 (tool_defs.py)       │
│  ├── 8 规划工具 (plan_tool_defs.py)   │
│  └── 10 自主工具 (auto_tool_defs.py)  │
│  → 调用 core/ 管理器操作 SQLite 数据   │
└──────────────────────────────────────┘
```

**换 UI 只需实现新的表现层，调用 `AgentLoop.run_turn()` 即可，核心逻辑零改动。**

---

## 关键设计

### 百万字级存储
- **SQLite 3**: 单文件 `wal.db`，17 张表 + FTS5 虚拟表，增量更新
- **毫秒级搜索**: FTS5 倒排索引全文检索
- **单文件备份**: 复制 `wal.db` 即备份；`create_checkpoint` 快照

### 上下文窗口保护
- **滑动窗口**: 保留最近 6 轮完整对话
- **摘要压缩**: 旧消息自动压缩为摘要
- **结果截断**: 文本 1500 字 / 列表 20 条 / 场景 500 字自动裁剪
- **RAG 注入**: 根据查询从 FTS5 检索相关片段注入

### 数据安全
- **检查点**: `create_checkpoint` / `rollback_to_checkpoint`（复制 wal.db）
- **YAML 导出**: `export_yaml_backup` 可读备份 + 跨系统迁移
- **自动备份**: 回滚前自动创建备份检查点

---

## 支持的模型

| 模型 | 适用场景 |
|------|---------|
| `deepseek-chat` (默认) | 日常写作、对话、管理操作 |
| `deepseek-reasoner` | 复杂剧情设计、逻辑推理、分析 |

兼容任何 OpenAI 兼容 API（修改 `-BaseUrl` 和 `-Model` 参数）。

---

## 升级路径

WAL 经过 9 个 Phase 的完整升级，从 YAML 单文件存储演进到 SQLite + FTS5 + 三种 Agent 模式的生产级系统。

| Phase | 功能 | 测试 |
|-------|------|------|
| 0 | SQLite 存储迁移 | — |
| 1 | 卷/部/篇层级 | — |
| 2 | 剧情层级 + 伏笔 | — |
| 3 | 角色快照 + FTS5 | — |
| 4 | 上下文窗口管理 | — |
| 5 | 章节导出 | — |
| 6 | Plan 规划模式 | 38 tests |
| 7 | Auto 自主模式 | 37 tests |
| 8 | 安静模式 + 集成 | 30 tests |
| **合计** | | **105 tests** |

---

## 许可

MIT
