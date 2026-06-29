"""Agent 核心逻辑 — 与 UI 层完全解耦

AgentLoop 管理：
  - 对话历史 (messages)
  - 工具调用循环 (think → act → observe → repeat)
  - 上下文注入
  - 模式切换 (Writing / Planning / Autonomous)

上层可以是 Terminal REPL、Web UI、GUI 等任意表现层。
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..engine.llm_client import LLMClient
from ..engine.context_manager import ContextManager, truncate_tool_result
from ..engine.emoji_strip import should_strip_emoji, strip_emoji
from .tool_defs import TOOL_DEFINITIONS, execute_tool
from .plan_tool_defs import PLAN_TOOL_DEFINITIONS, execute_plan_tool
from .auto_tool_defs import AUTO_TOOL_DEFINITIONS, execute_auto_tool
from .web_tool_defs import WEB_TOOL_DEFINITIONS, execute_web_tool
from .plan_mode import AgentMode, PLANNING_SYSTEM_PROMPT, AUTONOMOUS_SYSTEM_PROMPT, MODE_SWITCH_MESSAGES

def _strip_if_needed(text: str) -> str:
    """当终端不支持 Emoji 时，替换为 ASCII"""
    if should_strip_emoji():
        return strip_emoji(text)
    return text


# 系统提示词 — Agent 的「人格」（写作模式）
SYSTEM_PROMPT = """你是 WAL 小说写作助手，一个专业的 AI 小说创作搭档，专为百万字级长篇网文设计。

## 你的能力范围

### 故事管理
- 管理故事状态、章节结构、场景内容（支持 Part/Volume/Chapter 三级层级）
- 追踪剧情线（主线/卷级/支线/角色弧光），管理剧情交汇和情节点进度
- 维护角色档案、角色关系图谱、角色快照（按章节追踪角色演变）
- 世界观设定管理，包括地点、世界规则和时间线事件

### 写作辅助
- 获取章节/卷级写作上下文（含前一章摘要、剧情任务、出场角色）
- 撰写/续写场景内容，自动保存到数据库
- 章节导出（Markdown/HTML/纯文本/Word(docx)），支持单章/批量/卷/全书导出，支持按卷分文件或全书合并为单文件（总集）

### 智能检索
- FTS5 全文搜索：跨章节检索已写内容，毫秒级响应
- 快速回顾：按章节范围回顾特定主题的剧情
- 剧情健康检查：检测未收束支线、伏笔老化、主线支线比例

### 伏笔管理
- 记录、追踪、回收伏笔，自动检测到期提醒
- 伏笔健康度检查：标记超期未回收的伏笔

### 角色弧光
- 创建角色快照，追踪角色在各章节的成长变化
- 获取角色演变历程（人物弧光的完整脉络）

## 使用工具的原则
- 每次写作前，先用 get_chapter_context 或 get_chapter_context_text 获取上下文
- 涉及卷级规划时，用 get_volume_context 或 list_volumes 查看卷结构
- 写作前检查 plot_health_check 和 check_foreshadowing_health 了解健康度
- ⚠️ **【强制】写正文必须用 write_scene_content 工具保存！直接输出到对话中的文本不会被保存，上下文压缩后会永久丢失！**
- ⚠️ **写完一段正文后，立即调用 write_scene_content(chapter=N, scene_index=0, content="...") 保存到数据库**
- 写完每个场景后用 write_scene_content 保存，用 update_plot_point 更新进度
- **状态随故事演变**：角色性格/动机变了 → `update_character`，剧情线状态变了 → `update_plot_line`，伏笔信息变了 → `update_foreshadowing`，卷状态变了 → `update_volume`
- **数据清理**：有误创建的内容时，用 `delete_chapter`/`delete_scene`/`delete_volume`/`delete_plot_line`/`delete_character` 清理
- **重写章节**：先用 `get_chapter_artifacts(chapter_number=N)` 查看该章状态绑定，删除后级联自动清理，重写后重新记录
- 每章结束后用 create_character_snapshot 记录角色状态
- 定期调用 list_dangling_plots 确保没有遗漏支线
- 如需检索已写内容，用 search_story_index 全文搜索
- 如需回顾某段剧情，用 quick_review 快速浏览
- 如有需要，主动用 add_chapter、add_character、add_plot_line、add_foreshadowing 扩充故事
- 使用 add_foreshadowing 记录新伏笔，resolve_foreshadowing 收束伏笔
- 使用 get_character_evolution 查看角色成长轨迹
- 🌐 **联网搜索**：研究世界观设定（历史、地理、科技、文化）、查证事实时用 web_search 搜索；需要深入阅读某条结果时用 web_fetch 抓取页面正文。搜索结果仅作写作参考，不要原文照搬
- ⚡ **每次写作完成后，务必用 save_agent_memory 保存关键进度！** 对话会被压缩，记忆不会。至少记录：当前章节号、最新剧情发展、重要角色状态变化、下一步写作计划
- ⚡ **对话开始时，先用 get_agent_memory 回顾之前的写作进度**，不要凭"印象"写作
- ⚡ **每次切换模式或开始新话题前，保存当前状态到记忆**

## 持久记忆 vs 对话上下文
- 对话上下文（你看到的聊天记录）是**临时的**：最多保留 12 轮，超出部分会被压缩成简短摘要
- `save_agent_memory` 保存的是**永久记忆**：写入 SQLite 数据库，重启后依然存在
- **你要主动管理记忆**：写了新章节 → 保存进度；做了重要决策 → 记录决策；发现了问题 → 记录问题
- 重启后通过 `get_agent_memory` 恢复上下文，你的"记忆"不会丢失

## 三种工作模式
你可以通过 /plan、/write、/auto 命令切换模式：
- **写作模式 [Write]**（当前）：专注内容创作，使用全量写作工具
- **规划模式 [Plan]**：创意讨论、剧情分析、世界观构思（仅分析工具）
- **自主模式 [Auto]**：批量自主写作，支持检查点保护和决策审批

## 写作原则
- **主线驱动**：主线是故事骨架，每章都要推进主线
- **支线穿插**：支线在合适时机与主线交汇，不孤立发展
- **角色一致**：角色的行为、对话必须符合性格和动机
- **伏笔管理**：埋下的伏笔要有后续回收，用 add_foreshadowing 记录
- **节奏把控**：高潮与过渡交替，避免全程紧绷或全程松懈
- **卷级规划**：使用 Volume/Part 组织百万字级长篇结构
- **百万字规模**：所有数据存入 SQLite，支持高效查询和增量更新
- ⚠️ **字数达标**：每章有目标字数（word_count_target），以达标为默认目标。写完后用 get_chapter_context 检查 actual_word_count。不达标时：①内容还有空间 → 继续写实质内容；②叙事已自然收束 → 向用户报告"本章在 N 字处自然完结，是否需要调整目标"；③用户说够了 → 尊重决定。**叙事完整性优先于字数指标**，不得灌水凑数。作者对字数标准拥有最终否决权，可以随时用 update_chapter_info 修改 word_count_target

## 输出风格
- 用中文回复
- 写作时，先生成一段正文，再附上简要说明（推进了哪些剧情、角色状态变化）
- 管理操作时，简洁报告操作结果
- 使用 /quiet 可隐藏工具调用详情，/verbose 恢复显示
"""


class AgentLoop:
    """LLM Agent 核心循环 — 与 UI 无关"""

    def __init__(
        self,
        project_name: str,
        api_key: str | None = None,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",
        mode: AgentMode = AgentMode.WRITING,
        quiet_mode: bool = False,
        on_thinking: Callable[[str], None] | None = None,
        on_tool_call: Callable[[str, dict, str], None] | None = None,
        on_response: Callable[[str], None] | None = None,
        on_mode_switch: Callable[[AgentMode, AgentMode], None] | None = None,
    ):
        """
        Args:
            project_name: 小说项目名称
            api_key: API 密钥 (默认读 DEEPSEEK_API_KEY 环境变量)
            model: 模型名称
            base_url: API 地址
            mode: Agent 运行模式 (writing / planning / autonomous)
            quiet_mode: 安静模式 — True 时抑制工具调用回调通知
            on_thinking: 可选回调 — Agent 开始思考时调用
            on_tool_call: 可选回调 — 工具被调用时调用 (tool_name, args, result)
            on_response: 可选回调 — Agent 生成回复文本时调用
            on_mode_switch: 可选回调 — 模式切换时调用 (old_mode, new_mode)
        """
        self.project_name = project_name
        self.llm = LLMClient(api_key=api_key, model=model, base_url=base_url)
        self.mode = mode
        self.quiet_mode = quiet_mode

        # 根据模式选择工具集
        self._update_tools_for_mode()

        # 上下文窗口管理（百万字级核心）
        self.context_manager = ContextManager(max_tokens=90000, window_rounds=12)

        # 项目目录（RAG 检索用）
        proj_base = Path(os.environ.get("WAL_PROJECTS", "projects"))
        self.project_dir = str(proj_base / project_name)

        # 回调（UI 层通过它们获取实时信息）
        self.on_thinking = on_thinking
        self.on_tool_call = on_tool_call
        self.on_response = on_response
        self.on_mode_switch = on_mode_switch

        # 追踪当前轮是否用了 write_scene_content（防止正文丢失）
        self._used_write_scene = False

        # 对话历史
        self.messages: list[dict] = []

        # 尝试从磁盘恢复对话历史
        restored = self._load_conversation()

        # 注入/更新系统提示词
        if not restored or not self.messages:
            self._inject_system_prompt()
        else:
            # 替换 system prompt 为最新版本（模式可能已变，项目状态可能更新）
            fresh_system = self._build_system_prompt()
            if self.messages and self.messages[0].get("role") == "system":
                self.messages[0]["content"] = fresh_system
            else:
                self.messages.insert(0, {"role": "system", "content": fresh_system})

    def _build_system_prompt(self, for_mode: AgentMode | None = None) -> str:
        """构建完整的系统提示词（含项目概要）

        Args:
            for_mode: 目标模式，默认使用当前 self.mode
        """
        mode = for_mode if for_mode is not None else self.mode

        if mode == AgentMode.PLANNING:
            base_prompt = PLANNING_SYSTEM_PROMPT
        elif mode == AgentMode.AUTONOMOUS:
            base_prompt = AUTONOMOUS_SYSTEM_PROMPT
        else:
            base_prompt = SYSTEM_PROMPT

        # 附加项目概要
        try:
            from wal.agent.tools import get_story_status, list_plot_lines, list_dangling_plots

            status = get_story_status(self.project_name)
            if status.get("status") != "no story loaded":
                plots = list_plot_lines(self.project_name)
                dangling = list_dangling_plots(self.project_name)

                ctx = f"\n\n## 当前项目：《{status.get('name', self.project_name)}》\n"
                ctx += f"- 总章节：{status.get('total_chapters', 0)}章，已完成：{status.get('done_chapters', 0)}章\n"
                ctx += f"- 总字数：{status.get('total_words', 0)}字\n"
                ctx += f"- 剧情线：{len(plots)}条（未收束：{len(dangling)}条）\n"

                if dangling:
                    ctx += "\n⚠ 未收束支线：\n"
                    for dp in dangling[:5]:
                        ctx += f"  - {dp.get('name', '?')} ({dp.get('progress', 0)}%)\n"

                return _strip_if_needed(base_prompt + ctx)
        except Exception:
            pass

        return _strip_if_needed(base_prompt)

    def _inject_system_prompt(self) -> None:
        """注入系统提示词 + 当前项目信息（仅用于初始化，会替换整个 messages）"""
        self.messages = [
            {"role": "system", "content": self._build_system_prompt()},
        ]

    def _update_tools_for_mode(self) -> None:
        """根据当前模式更新工具集"""
        if self.mode == AgentMode.PLANNING:
            # 规划模式：8 个分析工具 + 只读数据查询工具 + 规划笔记 + 联网搜索 + 跨模式工具
            _READ_ONLY_TOOLS = {
                "get_story_status", "get_chapter_context", "list_dangling_plots",
                "list_characters", "get_character", "list_plot_lines",
                "plot_health_check", "character_relationship_map",
                "get_volume_context", "list_volumes", "get_plot_tree",
                "check_foreshadowing_health", "get_character_evolution",
                "search_story_index", "generate_chapter_summary", "quick_review",
                "export_outline", "suggest_next_scene",
                "get_custom_document", "list_custom_documents",
            }
            plan_names = {t["function"]["name"] for t in PLAN_TOOL_DEFINITIONS}
            web_names = {t["function"]["name"] for t in WEB_TOOL_DEFINITIONS}
            read_tools = [t for t in TOOL_DEFINITIONS
                          if t["function"]["name"] in _READ_ONLY_TOOLS
                          and t["function"]["name"] not in plan_names
                          and t["function"]["name"] not in web_names]
            self.tools = PLAN_TOOL_DEFINITIONS + WEB_TOOL_DEFINITIONS + read_tools
        elif self.mode == AgentMode.AUTONOMOUS:
            # 自主模式：自主工具 + 写作工具（去重，不含联网搜索——自主写作不应自行搜索，控制成本和安全）
            auto_names = {t["function"]["name"] for t in AUTO_TOOL_DEFINITIONS}
            deduped_writing = [t for t in TOOL_DEFINITIONS if t["function"]["name"] not in auto_names]
            self.tools = AUTO_TOOL_DEFINITIONS + deduped_writing
        else:
            # 写作模式：全量写作工具 + 联网搜索
            self.tools = TOOL_DEFINITIONS + WEB_TOOL_DEFINITIONS

    def switch_mode(self, new_mode: AgentMode) -> str:
        """切换 Agent 运行模式

        保留现有对话历史，仅更换系统提示词。
        上一模式的讨论、修改、共识都会被保留。

        Args:
            new_mode: 目标模式

        Returns:
            切换提示消息
        """
        if new_mode == self.mode:
            return f"已在 {self.mode.value} 模式中。"

        old_mode = self.mode
        self.mode = new_mode

        # 更新工具集
        self._update_tools_for_mode()

        # 保留对话历史，仅替换系统提示词
        # 不再调用 context_manager.reset() — 上下文窗口状态继续
        new_system_content = self._build_system_prompt()

        # 将模式切换上下文注入系统提示词（而非追加用户消息，避免干扰对话流）
        switch_msg = MODE_SWITCH_MESSAGES.get((old_mode, new_mode),
            f"已从 {old_mode.value} 模式切换到 {new_mode.value} 模式。")
        new_system_content += (
            f"\n\n## 模式切换记录\n"
            f"你刚从 **{old_mode.value}** 模式切换到 **{new_mode.value}** 模式。\n"
            f"{switch_msg}\n"
            f"上一模式的对话历史已保留，请基于已有的讨论和共识继续工作，不要从头开始。"
        )

        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = new_system_content
        else:
            self.messages.insert(0, {"role": "system", "content": new_system_content})

        # 通知 UI
        if self.on_mode_switch:
            self.on_mode_switch(old_mode, new_mode)

        return switch_msg

    def _execute_switch_mode(self, args: dict) -> str:
        """Agent 工具：切换工作模式（由 _handle_tool_calls 预分派调用）

        可供 LLM 通过 switch_mode 工具调用，实现自主模式切换。
        """
        mode_str = args.get("mode", "").strip().lower()
        mode_map = {
            "writing": AgentMode.WRITING,
            "planning": AgentMode.PLANNING,
            "autonomous": AgentMode.AUTONOMOUS,
            "write": AgentMode.WRITING,
            "plan": AgentMode.PLANNING,
            "auto": AgentMode.AUTONOMOUS,
        }
        new_mode = mode_map.get(mode_str)
        if new_mode is None:
            valid = "writing, planning, autonomous"
            return f"[Error] 无效模式 '{mode_str}'。可用模式：{valid}"
        msg = self.switch_mode(new_mode)
        return f"模式已切换：{msg}"

    # ============================================================
    #  对话持久化
    # ============================================================

    def _conversation_dir(self) -> Path:
        return Path(self.project_dir) / "conversation"

    def _save_conversation(self) -> None:
        """保存对话状态到磁盘（每次 turn 结束后调用）"""
        conv_dir = self._conversation_dir()
        try:
            conv_dir.mkdir(parents=True, exist_ok=True)

            messages_path = conv_dir / "messages.json"
            with open(messages_path, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2, default=str)

            summary_path = conv_dir / "summary.json"
            summary_data = {
                "running_summary": self.context_manager._running_summary,
                "summary_tokens": self.context_manager._summary_tokens,
                "saved_at": datetime.now().isoformat(),
            }
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, ensure_ascii=False, default=str)
        except Exception:
            pass  # 保存失败不影响主流程

    def _load_conversation(self) -> bool:
        """从磁盘恢复对话状态。成功返回 True。"""
        conv_dir = self._conversation_dir()
        messages_path = conv_dir / "messages.json"

        if not messages_path.exists():
            return False

        try:
            with open(messages_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, list) or len(loaded) == 0:
                return False
            self.messages = loaded
        except Exception:
            return False

        # 恢复上下文摘要
        summary_path = conv_dir / "summary.json"
        try:
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.context_manager._running_summary = data.get("running_summary", "")
                self.context_manager._summary_tokens = data.get("summary_tokens", 0)
        except Exception:
            pass

        return True

    def run_turn(self, user_input: str, stream_callback: Callable[[str], None] | None = None) -> str:
        """处理一轮用户输入，返回完整的 Agent 文本回复

        这是 UI 层的主要入口。内部执行 tool-calling 循环。

        Args:
            user_input: 用户输入文本
            stream_callback: 可选 — 流式接收最终回复的每个 token

        Returns:
            Agent 的完整文本回复
        """
        # 1. 添加用户消息到历史
        self.messages.append({"role": "user", "content": user_input})

        # 重置本轮追踪
        self._used_write_scene = False

        # 2. 上下文窗口管理 + RAG 检索注入
        self.messages = self.context_manager.manage(self.messages)
        self.messages = self.context_manager.inject_retrieved_context(
            self.messages, user_input, self.project_dir
        )

        # 3. 工具调用循环
        max_tool_rounds = 5
        for _ in range(max_tool_rounds):
            if self.on_thinking:
                self.on_thinking("思考中...")

            # 调用 LLM
            response = self.llm.chat_with_tools(
                self.messages, self.tools, temperature=0.7, max_tokens=16384
            )

            tool_calls = response.get("tool_calls")
            content = response.get("content", "")

            # 纯文本回复（无工具调用）→ 本轮结束
            if content and not tool_calls:
                self.messages.append({"role": "assistant", "content": content})

                if stream_callback:
                    stream_callback(content)

                if self.on_response:
                    self.on_response(content)

                self._save_conversation()
                return content

            # 有工具调用（可能附带文本说明）→ 执行后继续循环
            if tool_calls:
                self._handle_tool_calls(tool_calls, content=content or None)
                continue

        # 超时：强制 LLM 总结
        self.messages.append({"role": "user", "content": "请根据以上工具调用结果，给出最终回复。"})
        final = self.llm.chat_with_tools(self.messages, self.tools, temperature=0.7, max_tokens=16384)
        final_content = final.get("content", "（无法生成回复）")
        self.messages.append({"role": "assistant", "content": final_content})

        if self.on_response:
            self.on_response(final_content)

        self._save_conversation()
        return final_content

    def run_turn_stream(self, user_input: str) -> str:
        """处理一轮用户输入，通过回调流式输出文本

        返回完整文本。过程中调用 self.on_response 逐个 token 输出。
        """
        self.messages.append({"role": "user", "content": user_input})

        # 重置本轮追踪
        self._used_write_scene = False

        # 上下文窗口管理 + RAG 检索注入
        self.messages = self.context_manager.manage(self.messages)
        self.messages = self.context_manager.inject_retrieved_context(
            self.messages, user_input, self.project_dir
        )

        max_tool_rounds = 5
        for _ in range(max_tool_rounds):
            if self.on_thinking:
                self.on_thinking("思考中...")

            # 使用流式请求
            full_content = ""
            tool_calls_result = None

            for event in self.llm.chat_stream(self.messages, self.tools, temperature=0.7, max_tokens=16384):
                if event["type"] == "text":
                    full_content += event["text"]
                    if self.on_response:
                        self.on_response(event["text"])
                elif event["type"] == "tool_calls":
                    tool_calls_result = event["tool_calls"]

            if tool_calls_result:
                self._handle_tool_calls(tool_calls_result, content=full_content or None)
                continue

            if full_content.strip():
                self.messages.append({"role": "assistant", "content": full_content})
                self._save_conversation()
                return full_content

        # Fallback
        self.messages.append({"role": "user", "content": "请根据以上工具调用结果，给出最终回复。"})
        result = self.run_turn("", stream_callback=None)
        self._save_conversation()
        return result

    def reset(self) -> None:
        """重置对话历史（保留当前模式）"""
        self.messages = []
        self.context_manager.reset()
        self._inject_system_prompt()
        # 清除持久化对话文件
        try:
            conv_dir = self._conversation_dir()
            if conv_dir.exists():
                shutil.rmtree(str(conv_dir))
        except Exception:
            pass

    def get_mode(self) -> AgentMode:
        """获取当前 Agent 模式"""
        return self.mode

    def set_quiet_mode(self, enabled: bool) -> None:
        """设置安静模式

        Args:
            enabled: True = 隐藏工具调用详情, False = 显示工具调用
        """
        self.quiet_mode = enabled

    def get_quiet_mode(self) -> bool:
        """获取当前安静模式状态"""
        return self.quiet_mode

    def get_history(self) -> list[dict]:
        """获取对话历史（供 UI 层展示/导出）"""
        return self.messages

    # ============================================================
    #  内部方法
    # ============================================================

    def _handle_tool_calls(self, tool_calls: list[dict], content: str | None = None) -> None:
        """执行工具调用，将 assistant(tool_calls) + tool results 追加到消息历史

        Args:
            tool_calls: LLM 返回的工具调用列表
            content: LLM 同时附带的文本（如"让我先查看上下文..."），不会丢弃
        """
        # 1. 添加 assistant 消息（保留附带文本，不静默丢弃）
        self.messages.append({
            "role": "assistant",
            "content": content or None,
            "tool_calls": tool_calls,
        })

        # 2. 逐个执行工具并添加结果
        for tc in tool_calls:
            func_info = tc["function"]
            tool_name = func_info["name"]
            try:
                args = json.loads(func_info["arguments"])
            except json.JSONDecodeError:
                args = {}

            # 追踪持久化工具使用
            if tool_name in ("write_scene_content", "add_planning_note"):
                self._used_write_scene = True

            # 跨模式工具：预分派（不经过模式执行器）
            if tool_name == "switch_mode":
                result = self._execute_switch_mode(args)
            # 联网搜索工具：跨模式可用（Planning + Writing）
            elif tool_name in ("web_search", "web_fetch", "suggest_alternative_urls"):
                result = execute_web_tool(tool_name, args, self.project_name)
            # 根据模式选择工具执行器
            elif self.mode == AgentMode.PLANNING:
                # 先查规划工具，找不到则回退到写作工具（处理只读数据查询）
                plan_result = execute_plan_tool(tool_name, args, self.project_name)
                if "[Error] Unknown" in str(plan_result):
                    result = execute_tool(tool_name, args, self.project_name)
                else:
                    result = plan_result
            elif self.mode == AgentMode.AUTONOMOUS:
                # 自主模式：先查自主工具，再查写作工具
                auto_result = execute_auto_tool(tool_name, args, self.project_name)
                if "[Error] Unknown" in str(auto_result):
                    result = execute_tool(tool_name, args, self.project_name)
                else:
                    result = auto_result
            else:
                result = execute_tool(tool_name, args, self.project_name)

            # 截断超长工具结果（防止撑爆上下文）
            result_str = str(result)
            truncated = truncate_tool_result(result_str)

            # 通知 UI（传原始结果，UI 自己决定如何处理）
            # 安静模式下抑制工具调用通知
            if self.on_tool_call and not self.quiet_mode:
                self.on_tool_call(tool_name, args, truncated)

            # 添加 tool 消息（使用截断后的结果）
            self.messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": truncated,
            })
