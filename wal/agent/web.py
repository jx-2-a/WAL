"""WAL Web 入口 — 通过 AgentHub Web UI 使用 WAL 写作 Agent。

运行：python -m wal.agent.web --hub ws://host:port/ws/agent [--label 标签] [--project 项目名]
      也可由 AgentHub 以实例方式拉起（--hub/--label/--file-root 由 Hub 注入）。

架构（参照 agentweb SDK 线程模型，见 AgentHub PROTOCOL §4）：
- 主线程：WebSessionClient.run() — asyncio 事件循环，连接 Hub、收发事件。
- worker 线程：WebREPL.run() — WAL 对话循环（所有 _session 调用线程安全）。

I/O 映射：
- print/横幅 → _session.log（info/welcome/hint 等级气泡）
- 工具调用 → _session.tool_event（可展开工具卡）
- LLM 流式文本 → _session.stream_delta / stream_end
- DeepSeek 思考链 → _session.thinking_delta / thinking_end（可折叠思考块）
- 用户输入 → _session.ask；前提条件（选项目）→ _session.require 表单
- 运行时参数（模型/思考/温度）→ set_settings + on_setting 热重载
"""

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

# 确保项目根目录在 path 中（被 Hub 以 -m wal.agent.web 拉起时 cwd 已是 WAL 根，
# 这里兜底，保证独立从任意目录调用也能 import wal）
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .loop import AgentLoop
from .modes import AgentMode, MODE_SWITCH_MESSAGES

# 品牌色（web 端 log 不用 rich 颜色，仅作注释参考）
ACCENT = "#6C5CE7"

WELCOME_ASCII = r"""
  ╔╗ ╦ ╦  ╔═╗╔═╗╔╗╔╔╦╗
  ╠╩╗╚╦╝  ╔═╝║╣ ║║║ ║
  ╚═╝ ╩   ╚═╝╚═╝╝╚╝ ╩
  小说写作 Agent
"""

# 模型下拉候选（当前模型自动置顶）
_MODEL_OPTIONS = ["deepseek-v4-flash", "deepseek-v4-pro",
                  "deepseek-chat", "deepseek-reasoner"]


def _load_dotenv():
    """读 WAL 根 .env（DEEPSEEK_API_KEY / WAL_PROJECTS / SEARCH_BACKEND 等）。
    已存在的环境变量优先（被 Hub 拉起时 AGENT_HUB_INSTANCE 等不受影响）。"""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _projects_base() -> Path:
    """projects/ 目录（WAL_PROJECTS 支持自定义；相对路径以 WAL 根为准）。"""
    pb = Path(os.environ.get("WAL_PROJECTS", "projects"))
    if not pb.is_absolute():
        pb = _ROOT / pb
    try:
        pb.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return pb


def _list_projects() -> list[str]:
    """列出已有小说项目（projects/<name>/wal.db）。"""
    pb = _projects_base()
    if not pb.is_dir():
        return []
    return sorted(d.name for d in pb.iterdir()
                  if d.is_dir() and (d / "wal.db").exists())


# ---------------------------------------------------------------------------
# 恢复状态（sid + 项目）→ 重启续接会话、项目一次性不重问
# ---------------------------------------------------------------------------

def _state_path() -> Path:
    return _ROOT / "config" / "agent_state.json"


def _load_agent_state() -> dict:
    try:
        p = _state_path()
        if p.exists() and p.stat().st_size > 0:
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_agent_state(data: dict) -> None:
    try:
        p = _state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class WebREPL:
    """Web 对话循环 — 对标 TerminalREPL，把 AgentLoop 的 I/O 桥到 WebSessionClient。

    所有 _session 调用都在 worker 线程（线程安全）。
    """

    def __init__(self, session, project: str = "", api_key: str | None = None,
                 model: str = "deepseek-v4-flash",
                 base_url: str = "https://api.deepseek.com/v1",
                 mode: AgentMode = AgentMode.WRITING,
                 saved_state: dict | None = None, label: str = ""):
        self._session = session
        self._label = label
        self._saved = saved_state or {}
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._mode = mode
        self._runtime = {}          # 网页设置面板热重载值（model/thinking/temperature）
        self._last_settings = []    # 最近提交的设置 schema，on_setting 后重发刷新面板
        self._auto_task = ""        # 自主模式当前任务（每轮提醒注入）
        self.agent: AgentLoop | None = None
        self.project = project or ""   # 可被 _resolve_project 更新

    # ============================================================
    #  运行（worker 线程）
    # ============================================================

    def run(self) -> None:
        self._wait_connected()
        project = self._resolve_project()
        if not project:
            self._session.log("未选择项目，退出。", level="hint")
            self._session.stop()
            return
        self.project = project
        proj_dir = str(_projects_base() / project)

        # 上报分类信息 → Hub 更新会话/实例标签 + 文件服务定位
        self._session.set_meta(label=f"WAL·{project}", project_root=proj_dir)

        # 构建 Agent（项目选定后一次构建；对话历史从磁盘自动恢复）
        self.agent = AgentLoop(
            project_name=project,
            api_key=self._api_key,
            model=self._model,
            base_url=self._base_url,
            mode=self._mode,
            quiet_mode=False,
            on_thinking=self._on_thinking,
            on_tool_call=self._on_tool_call,
            on_response=None,
            on_mode_switch=self._on_mode_switch,
        )

        self._welcome()
        self._print_project_status()
        self._last_settings = self._build_settings_schema()
        self._session.set_settings(self._last_settings)

        turn = 0
        try:
            while True:
                self._session.set_status("")
                # 工具执行期间用户随时可发消息 → 优先消费引导
                guidance = self._session.poll_guidance()
                if guidance:
                    user_input = guidance
                else:
                    answer = self._session.ask(f"[{turn}] 你 > ")
                    if answer is None:
                        self._session.log("已中断，请继续输入。", level="hint")
                        continue
                    user_input = answer
                user_input = user_input.strip()
                if not user_input:
                    continue

                turn += 1
                self._session.user_message(user_input)   # 输入栏提交不留痕，补一笔气泡

                # ---- 特殊命令 ----
                if user_input.lower() in ("/clear", "清空"):
                    self.agent.reset()
                    self._session.log("对话历史已清空", level="info")
                    continue
                if user_input.lower() in ("/help", "帮助", "/h"):
                    self._print_help()
                    continue
                if user_input.lower() in ("/plan", "/p"):
                    self._switch_mode_command(AgentMode.PLANNING)
                    continue
                if user_input.lower() in ("/write", "/w"):
                    self._switch_mode_command(AgentMode.WRITING)
                    continue
                if user_input.lower() in ("/auto", "/a"):
                    self._switch_to_autonomous()
                    continue
                if user_input.lower() in ("/stop-auto", "/sa"):
                    self._switch_mode_command(AgentMode.WRITING)
                    continue
                if user_input.lower() in ("/quiet", "/q"):
                    self.agent.set_quiet_mode(True)
                    self._session.log("已开启安静模式（隐藏工具卡片）", level="info")
                    continue
                if user_input.lower() in ("/verbose", "/v"):
                    self.agent.set_quiet_mode(False)
                    self._session.log("已恢复详细模式（显示工具卡片）", level="info")
                    continue

                # ---- 普通回合 ----
                self._auto_task = user_input
                try:
                    self._do_turn(user_input)
                except Exception:
                    self._session.set_status("")
                    import traceback
                    self._session.log("[red]⚠ Agent 出错:[/red]", level="info")
                    self._session.log(traceback.format_exc()[-2000:], level="info")

                # ---- 自主模式：连续自动推进 ----
                if self.agent.mode == AgentMode.AUTONOMOUS:
                    self._auto_continue()
        finally:
            self._session.stop()

    def _wait_connected(self) -> None:
        """等 Hub 注册完成（拿到 sid）再做首个交互，避免 ask/require 发在注册前。"""
        while not getattr(self._session, "_sid", None) and not self._session._done.is_set():
            time.sleep(0.1)

    # ============================================================
    #  项目解析
    # ============================================================

    def _resolve_project(self) -> str:
        """项目解析顺序：--project > saved state（无 AGENT_HUB_FRESH）> label 命中 > require 表单。"""
        if self.project:
            return self.project
        if not os.environ.get("AGENT_HUB_FRESH") and self._saved.get("project"):
            saved = str(self._saved["project"]).strip()
            if saved and (_projects_base() / saved).is_dir():
                return saved
        if self._label and (_projects_base() / self._label).is_dir():
            return self._label
        return self._select_project_form()

    def _select_project_form(self) -> str:
        """require 表单选项目：select（已有项目）+ text（新建/自定义）。"""
        dirs = _list_projects()
        fields = []
        if dirs:
            fields.append({
                "key": "project", "label": "选择小说项目", "type": "select",
                "value": dirs[0],
                "options": [{"label": d, "value": d} for d in dirs],
            })
        fields.append({
            "key": "new", "label": "或输入新项目名", "type": "text",
            "placeholder": "留空则用上面的选择",
        })
        values = self._session.require("选择要操作的小说项目", fields)
        if not values or not isinstance(values, dict):
            return ""
        custom = (values.get("new") or "").strip()
        if custom:
            return custom
        return (values.get("project") or "").strip()

    # ============================================================
    #  AgentLoop → Web 回调桥接
    # ============================================================

    def _on_thinking(self, msg: str) -> None:
        self._session.set_status(str(msg))

    def _on_tool_call(self, tool_name: str, args: dict, result: str) -> None:
        """工具调用 → 工具卡片（start + end）。"""
        try:
            args = args or {}
            self._session.tool_event("start", name=tool_name, args=args)
            result_str = str(result)
            stripped = result_str.lstrip()
            if stripped.startswith("[Error]") or stripped.startswith("错误:"):
                self._session.tool_event("end", name=tool_name, ok=False,
                                         error=result_str[:2000])
            else:
                summary = result_str[:4000] if len(result_str) > 4000 else result_str
                self._session.tool_event("end", name=tool_name, ok=True,
                                         summary=summary or None)
        except Exception:
            pass

    def _on_mode_switch(self, old_mode: AgentMode, new_mode: AgentMode) -> None:
        """模式切换 → 完整切换说明（MODE_SWITCH_MESSAGES 同款），info 级气泡更醒目。"""
        msg = MODE_SWITCH_MESSAGES.get(
            (old_mode, new_mode),
            f"已从 {old_mode.value} 模式切换到 {new_mode.value} 模式。")
        self._session.log(msg, level="info")

    # ============================================================
    #  运行时设置面板（PROTOCOL §3 settings）
    # ============================================================

    def _build_settings_schema(self) -> list[dict]:
        model = self._runtime.get("model") or self.agent.llm.model
        thinking = bool(self.agent.llm.thinking)
        temp = self.agent.temperature
        max_tokens = int(self._runtime.get("max_tokens", 16384))
        effort = self._runtime.get("reasoning_effort") or self.agent.llm.reasoning_effort or "high"
        model_opts = [model] + [m for m in _MODEL_OPTIONS if m != model]
        return [
            {"key": "model", "label": "模型", "type": "select", "value": model,
             "options": [{"label": m, "value": m} for m in model_opts]},
            {"key": "thinking", "label": "思考模式", "type": "toggle", "value": thinking},
            {"key": "reasoning_effort", "label": "思考强度", "type": "select", "value": effort,
             "options": [{"label": "低 low", "value": "low"},
                         {"label": "高 high", "value": "high"},
                         {"label": "最大 max", "value": "max"}]},
            {"key": "temperature", "label": "Temperature", "type": "number", "value": temp},
            {"key": "max_tokens", "label": "Max Tokens", "type": "number", "value": max_tokens},
        ]

    def on_setting(self, key: str, value) -> None:
        """网页设置面板改动（settings_set）→ 热重载应用，并重发 settings 确认。"""
        self._runtime[key] = value
        if self.agent is None:
            return
        try:
            if key == "model":
                self.agent.llm.model = str(value)
                self._session.log(f"已应用: 模型 = {value}", level="info")
            elif key == "thinking":
                self.agent.llm.thinking = bool(value)
                self._session.log(f"已应用: 思考模式 = {'开' if value else '关'}", level="info")
            elif key == "reasoning_effort":
                self.agent.llm.reasoning_effort = str(value)
                self._session.log(f"已应用: 思考强度 = {value}", level="info")
            elif key == "temperature":
                self.agent.temperature = float(value)
                self._session.log(f"已应用: temperature = {value}", level="info")
            elif key == "max_tokens":
                self._runtime["max_tokens"] = int(value)
                self._session.log(f"已应用: max_tokens = {value}", level="info")
            # 更新本地 schema 对应项并重发 → 前端设置面板显示新值
            for s in self._last_settings:
                if s.get("key") == key:
                    s["value"] = value
            if self._last_settings:
                self._session.set_settings(self._last_settings)
        except Exception:
            pass

    # ============================================================
    #  流式回合（核心：精确的 stream / thinking 生命周期）
    # ============================================================

    def _do_turn(self, user_input: str) -> str:
        return self._stream_turn(user_input)

    def _stream_turn(self, user_input: str) -> str:
        agent = self.agent

        # 1. 追加用户消息 + 上下文管理 + RAG 注入（同 run_turn）
        agent.messages.append({"role": "user", "content": user_input})
        agent._used_write_scene = False
        agent._had_tool_calls = False
        agent.messages = agent.context_manager.manage(agent.messages)
        agent.messages = agent.context_manager.inject_retrieved_context(
            agent.messages, user_input, agent.project_dir)

        # 2. 工具调用循环（流式 + 思考链 + 工具卡生命周期）
        max_tool_rounds = 5
        max_tokens = int(self._runtime.get("max_tokens", 16384))
        interrupted = False
        for _ in range(max_tool_rounds):
            if self._check_interrupt():
                interrupted = True
                break
            self._session.set_status("思考中...")

            full = ""
            reasoning = ""
            tool_calls_result = None
            tool_reasoning = ""
            thinking_open = False
            try:
                for ev in agent.llm.chat_stream(
                        agent.messages, agent.tools,
                        temperature=agent.temperature, max_tokens=max_tokens):
                    if self._check_interrupt():
                        interrupted = True
                        break
                    t = ev["type"]
                    if t == "text":
                        full += ev["text"]
                        self._session.stream_delta(ev["text"])
                    elif t == "reasoning":
                        reasoning += ev["content"]
                        self._session.thinking_delta(ev["content"])
                        thinking_open = True
                    elif t == "tool_calls":
                        tool_calls_result = ev["tool_calls"]
                        tool_reasoning = ev.get("reasoning_content", "")
            except Exception as e:
                self._session.thinking_end()
                self._session.stream_end(None)
                self._session.set_status("")
                self._session.log(f"[red]LLM 请求出错: {e}[/red]", level="info")
                return ""

            if interrupted:
                break
            if thinking_open:
                self._session.thinking_end()   # 思考结束/转工具都必须收思考块
                thinking_open = False

            # 有工具调用 → 收尾前言流 → 执行工具 → 继续下一轮
            if tool_calls_result:
                if full.strip():
                    self._session.stream_end(full)
                else:
                    self._session.stream_end(None)
                agent._handle_tool_calls(
                    tool_calls_result, content=full or None,
                    reasoning_content=tool_reasoning or reasoning or None)
                # 工具批后检查用户引导（网页随时可发消息）
                g = self._session.poll_guidance()
                if g:
                    self._session.user_message(g)
                    agent.messages.append({"role": "user", "content": g})
                continue

            # 纯文本回复 → 完成
            if full.strip():
                self._session.stream_end(full)
                agent.messages.append({"role": "assistant", "content": full})
                agent._save_conversation()
                self._session.set_status("")
                return full

            # 防御：空回复不静默
            self._session.stream_end(None)
            self._session.set_status("")
            self._session.log("⚠ LLM 返回了空回复，请重试。", level="hint")
            return ""

        # 3. 打断 / 轮数耗尽
        self._session.stream_end(None)
        self._session.set_status("")
        if interrupted:
            self._session.log("已打断。", level="hint")
            return ""

        # 轮数耗尽：强制 LLM 总结（同 run_turn 回退）
        agent.messages.append({"role": "user", "content": "请根据以上工具调用结果，给出最终回复。"})
        try:
            resp = agent.llm.chat(agent.messages, agent.tools,
                                  temperature=agent.temperature, max_tokens=max_tokens)
        except Exception as e:
            resp = {"content": f"[Error] {e}"}
        final = resp.get("content", "") or ""
        if final:
            agent.messages.append({"role": "assistant", "content": final})
            self._session.stream_end(final)
        else:
            self._session.stream_end(None)
        agent._save_conversation()
        self._session.set_status("")
        return final

    def _check_interrupt(self) -> bool:
        """网页『打断』按钮 → 中断标志。"""
        return self._session.pop_interrupt()

    # ============================================================
    #  自主模式连续推进
    # ============================================================

    def _switch_mode_command(self, new_mode: AgentMode) -> None:
        """模式切换命令（/plan /write /stop-auto）。

        实际切换由 on_mode_switch 回调报完整说明；**同模式**时 switch_mode 不触发
        回调 → 手动补一条「已在 X 模式中。」，避免用户以为没反应。
        """
        old = self.agent.mode
        msg = self.agent.switch_mode(new_mode)
        if self.agent.mode == old:
            self._session.log(msg, level="info")

    def _switch_to_autonomous(self) -> None:
        old = self.agent.mode
        msg = self.agent.switch_mode(AgentMode.AUTONOMOUS)
        if self.agent.mode == old:
            # 已在自主模式：switch_mode 不触发回调 → 补一条
            self._session.log(msg, level="info")
            return
        self.agent.reset_auto_counters()
        self._session.log("自主模式 — 设定方向后自动推进；每轮之间 2s 倒计时可点击打断", level="info")

    def _auto_continue(self) -> None:
        task = self._auto_task
        while self.agent.mode == AgentMode.AUTONOMOUS:
            self._session.set_status("自主模式 · 2s 后自动继续，可点击打断")
            woke = self._session.sleep(2.0)
            if not woke:
                self._session.set_status("")
                self._session.log("自主模式已暂停。输入指令继续，或 /stop-auto 退出。", level="hint")
                return
            # 用户引导优先
            g = self._session.poll_guidance()
            if g:
                self._session.user_message(g)
                self._auto_task = g
                try:
                    self._do_turn(g)
                except Exception:
                    import traceback
                    self._session.log(traceback.format_exc()[-2000:], level="info")
                continue
            # 每轮注入任务提醒，防止遗忘目标或空转
            reminder = (
                "继续推进。\n\n"
                "[自主模式任务提醒]\n"
                f"当前任务：{task}\n"
                "如果此任务已完成，请调用 end_auto_session 暂停，不要空转。"
            )
            try:
                self._do_turn(reminder)
            except Exception:
                import traceback
                self._session.log(traceback.format_exc()[-2000:], level="info")
            stop_reason = self.agent.check_auto_stop_reason()
            if stop_reason:
                self._session.set_status("")
                self._session.log(f"✓ {stop_reason}", level="info")
                self._session.log("自主模式已暂停。输入指令继续，或 /stop-auto 退出。", level="hint")
                return

    # ============================================================
    #  展示辅助
    # ============================================================

    def _welcome(self) -> None:
        self._session.log(WELCOME_ASCII, level="welcome")
        self._session.log(f"项目：{self.project} ｜ 模型：{self.agent.llm.model}", level="info")
        self._session.log(
            "对话命令：/plan · /write · /auto · /stop-auto · /clear · /help\n"
            "随时可在输入栏发消息打断或引导；右上角设置面板可改模型/思考/思考强度/温度/Max Tokens",
            level="hint")

    def _print_project_status(self) -> None:
        try:
            from wal.agent.tools import get_story_status, list_plot_lines, list_dangling_plots
            status = get_story_status(self.project)
            if status.get("status") == "no story loaded":
                self._session.log("项目未加载，请先创建故事。", level="info")
                return
            plots = list_plot_lines(self.project)
            dangling = list_dangling_plots(self.project)
            lines = [
                f"故事：{status['name']}",
                f"进度：{status['done_chapters']}/{status['total_chapters']} 章完成 ({status['progress_percent']}%)",
                f"总字数：{status['total_words']}",
                f"剧情线：{len(plots)} 条 | 未收束：{len(dangling)} 条",
            ]
            self._session.log("\n".join(lines), level="info")
        except Exception as e:
            self._session.log(f"（无法加载项目状态: {e}）", level="info")

    def _print_help(self) -> None:
        mode_name = self.agent.mode.value
        text = (
            "可用命令：\n"
            "  /plan /p        切换到规划模式（创意讨论、分析构思）\n"
            "  /write /w       切换到写作模式（内容产出、管理操作）\n"
            "  /auto /a        切换到自主模式（自动推进写作）\n"
            "  /stop-auto /sa  退出自主模式，回到写作模式\n"
            "  /clear          清空对话历史\n"
            "  /quiet /q       隐藏工具卡片\n"
            "  /verbose /v     恢复显示工具卡片\n"
            "  /help /h        显示此帮助\n"
            "\n"
            f"当前模式：{mode_name} ｜ 安静模式：{'开' if self.agent.quiet_mode else '关'}"
        )
        self._session.log(text, level="info")


# ===========================================================================
#  入口
# ===========================================================================

def main():
    _load_dotenv()
    parser = argparse.ArgumentParser(
        description="WAL 小说写作 Agent（Web 模式，连 AgentHub）",
        epilog="一键启动：在 AgentHub 网页里启动 WAL 实例，或手动 --hub ws://host:port/ws/agent")
    parser.add_argument("--hub", nargs="?", const=True, default=None,
                        help="连接 AgentHub。传 ws://host:port/ws/agent，或 --hub 用环境变量 AGENT_HUB")
    parser.add_argument("--label", default=os.environ.get("AGENT_LABEL", ""),
                        help="Hub 会话显示名（默认 AGENT_LABEL 或项目名）")
    parser.add_argument("--file-root", action="append", default=[],
                        help="Hub 文件服务根目录（可多次），默认 AGENT_FILE_ROOTS 分号分隔")
    parser.add_argument("--project", default="", help="小说项目名称（默认自动选择/恢复）")
    parser.add_argument("--model", default="deepseek-v4-flash", help="LLM 模型 (默认: deepseek-v4-flash)")
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1", help="API 地址")
    parser.add_argument("--api-key", default=None, help="API Key (默认从 .env / 环境变量读取)")
    parser.add_argument("--mode", default="writing",
                        choices=["writing", "planning", "autonomous"],
                        help="Agent 启动模式 (默认: writing)")
    args = parser.parse_args()

    hub = args.hub if args.hub is not True else os.environ.get("AGENT_HUB", "").strip()
    if not hub:
        sys.exit("WAL Web 模式必须连接 AgentHub：用 --hub ws://host:port/ws/agent 或设置 AGENT_HUB 环境变量")
    if not hub.startswith("ws://") and not hub.startswith("wss://"):
        hub = "ws://" + hub

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        sys.exit("[ERROR] DEEPSEEK_API_KEY 未设置！请在 .env 或环境变量中配置")

    file_roots = list(args.file_root)
    if not file_roots:
        file_roots = [p.strip() for p in os.environ.get("AGENT_FILE_ROOTS", "").split(";") if p.strip()]
    if not file_roots:
        file_roots = [str(_projects_base())]

    mode_map = {
        "writing": AgentMode.WRITING,
        "planning": AgentMode.PLANNING,
        "autonomous": AgentMode.AUTONOMOUS,
    }

    # 恢复状态（重启续接）
    # AGENT_HUB_FRESH=1（Hub 新建实例）：开新会话（清 sid），但**保留项目**——
    # 项目是我们自己选的小说，不该每次重启都重新选。
    saved = _load_agent_state()
    if os.environ.get("AGENT_HUB_FRESH"):
        saved = {"project": saved.get("project", "")}
    resume_sid = (saved.get("sid") or "").strip() or None

    from agentweb.client import WebSessionClient
    session = WebSessionClient(
        hub_url=hub,
        label=args.label or "WAL",
        file_roots=file_roots,
        resume_sid=resume_sid,
    )
    repl = WebREPL(
        session,
        project=args.project,
        api_key=api_key,
        model=args.model,
        base_url=args.base_url,
        mode=mode_map[args.mode],
        saved_state=saved,
        label=session._label,
    )
    session.on_setting = repl.on_setting

    # 注册成功即落盘 sid、项目选定再落盘 → Hub 重启硬杀也不丢恢复状态
    def _autosave():
        last = None
        while True:
            sid = getattr(session, "_sid", None)
            proj = repl.project or ""
            sig = (sid, proj)
            if sid and sig != last:
                _save_agent_state({"sid": sid, "project": proj})
                last = sig
            time.sleep(1)

    threading.Thread(target=_autosave, daemon=True).start()
    threading.Thread(target=repl.run, daemon=True).start()
    try:
        session.run()
    finally:
        # 结束：保存恢复状态（sid + 项目）→ 下次重启自动续接
        if session._sid:
            _save_agent_state({"sid": session._sid, "project": repl.project or ""})


if __name__ == "__main__":
    main()
