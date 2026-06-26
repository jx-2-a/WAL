"""Terminal REPL — 基于 AgentLoop 的终端交互界面

使用 rich 美化输出。分层设计：此文件只负责表现层，
核心逻辑全部在 AgentLoop (core.py) 中，可被任何 UI 复用。
"""

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.spinner import Spinner

from .core import AgentLoop
from .plan_mode import AgentMode

# 品牌色
ACCENT = "#6C5CE7"
WARN = "#FDCB6E"
ERROR = "#E17055"
SUCCESS = "#00B894"
TOOL_COLOR = "#74B9FF"
PLAN_COLOR = "#F39C12"   # 规划模式 - 橙色
WRITE_COLOR = "#6C5CE7"  # 写作模式 - 紫色
AUTO_COLOR = "#E74C3C"   # 自主模式 - 红色

WELCOME_ASCII = r"""
  ╔╗ ╦ ╦  ╔═╗╔═╗╔╗╔╔╦╗
  ╠╩╗╚╦╝  ╔═╝║╣ ║║║ ║
  ╚═╝ ╩   ╚═╝╚═╝╝╚╝ ╩
  小说写作 Agent
"""


class TerminalREPL:
    """交互式终端 Agent — WAL 的默认 CLI 界面"""

    def __init__(self, project_name: str, api_key: str | None = None,
                 model: str = "deepseek-chat", base_url: str = "https://api.deepseek.com/v1",
                 mode: AgentMode = AgentMode.WRITING, quiet: bool = False):
        self.project_name = project_name
        self.console = Console()
        self.current_mode = mode

        # 安静模式 — 初始值，后续从 agent_config 加载
        self.quiet_mode = quiet

        # 尝试从 agent_config 加载持久化的 quiet_mode
        try:
            from wal.core.auto_manager import AutoManager
            proj_base = Path(os.environ.get("WAL_PROJECTS", "projects"))
            proj_dir = str(proj_base / project_name)
            am = AutoManager(proj_dir)
            saved_quiet = am.repo.get_config("quiet_mode", "")
            if saved_quiet == "true":
                self.quiet_mode = True
                quiet = True
            elif saved_quiet == "false":
                self.quiet_mode = False
                quiet = False
            # 加载持久化的模式
            saved_mode = am.repo.get_config("default_mode", "")
            if saved_mode and saved_mode in ("writing", "planning", "autonomous"):
                mode = AgentMode(saved_mode)
                self.current_mode = mode
        except Exception:
            pass  # 项目不存在或加载失败，使用默认值

        # 创建 Agent 核心，注入 UI 回调
        self.agent = AgentLoop(
            project_name=project_name,
            api_key=api_key,
            model=model,
            base_url=base_url,
            mode=mode,
            quiet_mode=quiet,
            on_thinking=self._on_thinking,
            on_tool_call=self._on_tool_call,
            on_response=self._on_response,
            on_mode_switch=self._on_mode_switch,
        )

        self._stream_buffer: list[str] = []
        self._tool_count = 0

    # ============================================================
    #  回调 — AgentLoop → UI
    # ============================================================

    def _on_thinking(self, msg: str) -> None:
        """Agent 开始思考"""
        pass  # 暂不显示，避免刷屏

    def _on_tool_call(self, tool_name: str, args: dict, result: str) -> None:
        """工具被调用时显示"""
        self._tool_count += 1
        args_str = ", ".join(f"{k}={v}" for k, v in args.items())
        tool_panel = Panel(
            f"[bold]{tool_name}[/bold]({args_str})\n\n[dim]{result[:500]}[/dim]",
            title=f"[{TOOL_COLOR}]Tool Call #{self._tool_count}[/{TOOL_COLOR}]",
            border_style=TOOL_COLOR,
            padding=(0, 1),
        )
        self.console.print(tool_panel)

    def _on_response(self, text: str) -> None:
        """收到回复文本（逐 token 流式）"""
        self._stream_buffer.append(text)

    def _on_mode_switch(self, old_mode: AgentMode, new_mode: AgentMode) -> None:
        """模式切换回调"""
        self.current_mode = new_mode
        if new_mode == AgentMode.PLANNING:
            color = PLAN_COLOR
            label = "[Plan]"
        elif new_mode == AgentMode.AUTONOMOUS:
            color = AUTO_COLOR
            label = "[Auto]"
        else:
            color = WRITE_COLOR
            label = "[Write]"
        try:
            self.console.print(f"\n[{color}]{label} 已切换到 {new_mode.value} 模式[/{color}]")
        except UnicodeEncodeError:
            pass

    # ============================================================
    #  运行 REPL
    # ============================================================

    def run(self) -> None:
        """启动 REPL 主循环

        写作/规划模式：等待用户输入 → 处理 → 等待输入（手动循环）
        自主模式：用户说话 → Agent 连续循环自动推进 → 按 Enter 暂停说话 → 继续循环
        """
        self._print_welcome()

        # 显示初始故事状态
        self._print_project_status()

        while True:
            # ---- 模式指示器 ----
            if self.current_mode == AgentMode.PLANNING:
                mode_color = PLAN_COLOR
            elif self.current_mode == AgentMode.AUTONOMOUS:
                mode_color = AUTO_COLOR
            else:
                mode_color = ACCENT
            mode_label = self.current_mode.value.upper()

            # ---- 获取用户输入 ----
            try:
                if self.current_mode == AgentMode.AUTONOMOUS:
                    prompt = (
                        f"\n[bold {AUTO_COLOR}][AUTO] 你说 >[/bold {AUTO_COLOR}] "
                    )
                else:
                    prompt = f"\n[bold {mode_color}][{mode_label}] You >[/bold {mode_color}] "
                user_input = self.console.input(prompt)
            except (KeyboardInterrupt, EOFError):
                if self.current_mode == AgentMode.AUTONOMOUS:
                    # Ctrl+C 在自主模式提示符下：只显示提示，不退出
                    self.console.print(
                        f"\n[{WARN}]已暂停。输入指令后继续，或 /sa 退出自主模式[/{WARN}]"
                    )
                    continue
                else:
                    self.console.print(f"\n[{WARN}]再见！[/{WARN}]")
                    break

            user_input = user_input.strip()
            if not user_input:
                continue

            # ---- 特殊命令（所有模式通用） ----
            if user_input.lower() in ("exit", "quit", "q", "退出"):
                self.console.print(f"[{WARN}]再见！[/{WARN}]")
                break
            if user_input.lower() in ("/clear", "清空"):
                self.agent.reset()
                self.console.print(f"[{SUCCESS}]对话历史已清空[/{SUCCESS}]")
                continue
            if user_input.lower() in ("/help", "帮助"):
                self._print_help()
                continue
            if user_input.lower() in ("/plan", "/p"):
                self._switch_to_planning()
                continue
            if user_input.lower() in ("/write", "/w"):
                self._switch_to_writing()
                continue
            if user_input.lower() in ("/auto", "/a"):
                self._switch_to_autonomous()
                self.console.print(
                    f"\n[{AUTO_COLOR}]━━━ 自主模式 — 等你说完就开始自动推进 ━━━[/{AUTO_COLOR}]"
                )
                self.console.print(
                    f"[dim]轮间按 Enter 暂停，Ctrl+C 强制中断，/sa 退出[/dim]"
                )
                continue
            if user_input.lower() in ("/stop-auto", "/sa"):
                self._stop_autonomous()
                continue
            if user_input.lower() in ("/quiet", "/q"):
                self._set_quiet_mode(True)
                continue
            if user_input.lower() in ("/verbose", "/v"):
                self._set_quiet_mode(False)
                continue

            # ---- 处理 Agent 回合 ----
            self._do_agent_turn(user_input)

            # ---- 自主模式：进入连续自动循环 ----
            if self.current_mode == AgentMode.AUTONOMOUS:
                while self.current_mode == AgentMode.AUTONOMOUS:
                    # 轮间等待：按 Enter 暂停，超时自动继续
                    paused = self._wait_for_pause(2.0)
                    if paused:
                        self.console.print(
                            f"\n[{WARN}]自主模式已暂停。输入指令后继续，或 /sa 退出[/{WARN}]"
                        )
                        break  # 退出内层循环，回到外层等待用户输入
                    try:
                        self.console.print(f"\n[dim]── 自主继续 ──[/dim]")
                        self._do_agent_turn("继续")
                    except KeyboardInterrupt:
                        # Ctrl+C 在 API 调用期间仍可强制中断
                        self.console.print(
                            f"\n[{WARN}]已中断。输入指令后继续，或 /sa 退出[/{WARN}]"
                        )
                        break

    def _do_agent_turn(self, user_input: str) -> None:
        """执行一轮 Agent 对话（提取公共逻辑，避免重复）"""
        self._tool_count = 0
        self._stream_buffer = []

        agent_color = {
            AgentMode.PLANNING: PLAN_COLOR,
            AgentMode.AUTONOMOUS: AUTO_COLOR,
            AgentMode.WRITING: ACCENT,
        }.get(self.current_mode, ACCENT)
        agent_label = f"Agent [{self.current_mode.value}]"
        self.console.print(f"\n[bold {agent_color}]{agent_label} >[/bold {agent_color}]")
        self.console.print("─" * 60)

        try:
            response = self.agent.run_turn(user_input)

            if response:
                md = Markdown(response, code_theme="monokai")
                self.console.print(md)

        except Exception as e:
            self.console.print(f"[{ERROR}]错误: {e}[/{ERROR}]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

        self.console.print("─" * 60)

    def _wait_for_pause(self, timeout: float = 2.0) -> bool:
        """轮间等待：用户按 Enter 返回 True（暂停），超时返回 False（继续）

        使用平台相关的非阻塞输入检测，不依赖 Ctrl+C。
        Windows: msvcrt.kbhit() 轮询
        Unix: select.select() 超时检测
        """
        import sys

        self.console.print(
            f"[dim]（{timeout:.0f}s 后自动继续，按 [bold]Enter[/bold] 暂停...）[/dim]",
            end=" ",
        )

        if sys.platform == "win32":
            import msvcrt
            import time as _time
            deadline = _time.time() + timeout
            while _time.time() < deadline:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b"\r", b"\n"):  # Enter 键
                        # 消耗掉后续缓冲字符
                        while msvcrt.kbhit():
                            msvcrt.getch()
                        self.console.print("")  # 换行
                        return True
                    # 其他按键忽略，继续等待
                _time.sleep(0.1)
            self.console.print("")  # 超时，换行
            return False
        else:
            import select
            self.console.print("")
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if ready:
                sys.stdin.readline()  # 消耗输入行
                return True
            return False

    def _print_welcome(self) -> None:
        """打印欢迎画面"""
        self.console.print(f"[bold {ACCENT}]{WELCOME_ASCII}[/bold {ACCENT}]", justify="center")
        self.console.print(f"[dim]项目：{self.project_name}[/dim]", justify="center")
        self.console.print(f"[dim]模型：{self.agent.llm.model}[/dim]", justify="center")
        self.console.print(f"[dim]输入 /help 查看帮助，exit 退出[/dim]\n", justify="center")

    def _print_project_status(self) -> None:
        """显示当前项目状态"""
        try:
            from wal.agent.tools import get_story_status, list_dangling_plots, list_plot_lines

            status = get_story_status(self.project_name)
            if status.get("status") == "no story loaded":
                self.console.print(f"[{WARN}]项目未加载，请先创建故事。[/{WARN}]")
                return

            plots = list_plot_lines(self.project_name)
            dangling = list_dangling_plots(self.project_name)

            status_lines = [
                f"故事：[bold]{status['name']}[/bold]",
                f"进度：{status['done_chapters']}/{status['total_chapters']} 章完成 ({status['progress_percent']}%)",
                f"总字数：{status['total_words']}",
                f"剧情线：{len(plots)} 条 | 未收束：[{WARN}]{len(dangling)}[/{WARN}] 条",
            ]
            panel = Panel(
                "\n".join(status_lines),
                title="[bold]当前状态[/bold]",
                border_style=ACCENT,
            )
            self.console.print(panel)
        except Exception as e:
            self.console.print(f"[dim]（无法加载项目状态: {e}）[/dim]")

    def _switch_to_planning(self) -> None:
        """切换到规划模式"""
        msg = self.agent.switch_mode(AgentMode.PLANNING)
        self.current_mode = AgentMode.PLANNING
        try:
            self.console.print(f"\n[{PLAN_COLOR}]{msg}[/{PLAN_COLOR}]")
        except UnicodeEncodeError:
            self.console.print(f"\n[{PLAN_COLOR}]已切换到 planning 模式[/{PLAN_COLOR}]")

    def _switch_to_writing(self) -> None:
        """切换到写作模式"""
        msg = self.agent.switch_mode(AgentMode.WRITING)
        self.current_mode = AgentMode.WRITING
        try:
            self.console.print(f"\n[{WRITE_COLOR}]{msg}[/{WRITE_COLOR}]")
        except UnicodeEncodeError:
            self.console.print(f"\n[{WRITE_COLOR}]已切换到 writing 模式[/{WRITE_COLOR}]")

    def _switch_to_autonomous(self) -> None:
        """切换到自主模式（仅切换模式，不启动独立循环）

        模式切换后回到主 REPL 循环：
        - 用户先说（给方向/指令）
        - Agent 处理后自动进入连续循环
        - Ctrl+C 暂停循环，用户说话
        - 用户说完继续循环
        """
        msg = self.agent.switch_mode(AgentMode.AUTONOMOUS)
        self.current_mode = AgentMode.AUTONOMOUS
        try:
            self.console.print(f"\n[{AUTO_COLOR}]{msg}[/{AUTO_COLOR}]")
        except UnicodeEncodeError:
            self.console.print(f"\n[{AUTO_COLOR}]已切换到 autonomous 模式[/{AUTO_COLOR}]")

        # 不启动独立循环 — 主 REPL 循环会根据模式自动处理

    def _stop_autonomous(self) -> None:
        """退出自主模式，回到写作模式"""
        if self.current_mode == AgentMode.AUTONOMOUS:
            self._switch_to_writing()
        else:
            self.console.print(f"[{WARN}]当前不在自主模式中[/{WARN}]")

    def _set_quiet_mode(self, enabled: bool) -> None:
        """切换安静模式"""
        self.quiet_mode = enabled
        self.agent.set_quiet_mode(enabled)

        # 持久化到 agent_config
        try:
            from wal.core.auto_manager import AutoManager
            proj_base = Path(os.environ.get("WAL_PROJECTS", "projects"))
            proj_dir = str(proj_base / self.project_name)
            am = AutoManager(proj_dir)
            am.repo.set_config("quiet_mode", "true" if enabled else "false")
        except Exception:
            pass

        if enabled:
            self.console.print(f"[{SUCCESS}][Quiet] 安静模式已开启 — 工具调用将不再显示[/{SUCCESS}]")
        else:
            self.console.print(f"[{SUCCESS}][Verbose] 详细模式已恢复 — 工具调用将正常显示[/{SUCCESS}]")

    def _print_help(self) -> None:
        """打印帮助"""
        if self.current_mode == AgentMode.PLANNING:
            mode_name = "规划模式 [Planning]"
        elif self.current_mode == AgentMode.AUTONOMOUS:
            mode_name = "自主模式 [Auto]"
        else:
            mode_name = "写作模式 [Writing]"

        help_text = f"""
## 可用命令

| 命令 | 说明 |
|------|------|
| `exit` / `quit` / `退出` | 退出 Agent |
| `/clear` / `清空` | 清空对话历史 |
| `/help` / `帮助` | 显示此帮助 |
| `/plan` / `/p` | 切换到规划模式（创意讨论、分析构思） |
| `/write` / `/w` | 切换到写作模式（内容产出、管理操作） |
| `/auto` / `/a` | 切换到自主模式（自动推进写作） |
| `/stop-auto` / `/sa` | 退出自主模式，回到写作模式 |
| `/quiet` / `/q` | 开启安静模式（隐藏工具调用详情） |
| `/verbose` / `/v` | 恢复详细模式（显示工具调用） |

当前模式：**{mode_name}** | 安静模式：**{'开启' if self.quiet_mode else '关闭'}**

"""

        if self.current_mode == AgentMode.PLANNING:
            help_text += """
## 规划模式 — 可用的规划工具

| 工具 | 用途 |
|------|------|
| `suggest_plot_direction` | 分析剧情现状，建议发展方向 |
| `brainstorm_character_arc` | 为角色构思弧光 |
| `analyze_plot_holes` | 检测剧情漏洞 |
| `propose_plot_twist` | 构思剧情转折 |
| `evaluate_pacing` | 评估故事节奏 |
| `suggest_conflict_escalation` | 建议冲突升级方案 |
| `brainstorm_world_building` | 构思世界观扩展 |
| `analyze_theme_consistency` | 检查主题一致性 |

## 你可以这样说

```
分析一下目前的剧情漏洞
给叶凡构思一个角色弧光
评估第1章到第10章的节奏
有什么好的剧情转折方向？
世界观还有哪些可以扩展的地方？
```
"""
        elif self.current_mode == AgentMode.AUTONOMOUS:
            help_text += """
## 自主模式 — 可用的自主控制工具

| 工具 | 用途 |
|------|------|
| `set_autonomy_level` | 设置自主等级 |
| `set_direction` | 设置写作方向/目标 |
| `start_auto_session` | 开始自主会话 |
| `end_auto_session` | 结束自主会话 |
| `create_checkpoint` | 创建数据库检查点（备份） |
| `rollback_to_checkpoint` | 回滚到检查点 |
| `list_checkpoints` | 列出所有检查点 |
| `approve_decision` | 审批通过决策 |
| `reject_decision` | 拒绝决策 |
| `get_auto_status` | 获取自主模式状态 |

自主模式下，Agent 拥有完整的写作工具 + 自主控制工具。
使用 `/stop-auto` 退出自主模式。
"""
        else:
            help_text += """
## 写作模式 — 你可以这样说

```
帮我看看目前的剧情进度
第3章该怎么写？给我写作上下文
帮我写第1章的第一个场景
检查一下剧情健康度
叶凡的角色档案是什么？
给我列出所有未收束的支线
添加一个角色：林婉儿，主角的师姐
把主线-崛起之路 的第3个情节点标记为完成
```
"""
        self.console.print(Markdown(help_text))
