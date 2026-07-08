"""WAL 终端窗口 — pyte 终端模拟器 + tkinter Canvas 渲染

架构对标 VS Code:  xterm.js (JS) → pyte (Python)
                   Electron     → tkinter
"""

import os
import re
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import font as tkfont

import pyte
from pyte.screens import HistoryScreen

from wal.gui.theme import (
    BG_DARK, BG_MID, BG_INPUT,
    FG_PRIMARY, FG_SECONDARY, FG_ACCENT, FG_GREEN, FG_YELLOW,
    FONT_FAMILY, FONT_BOLD, FONT_NORMAL,
)

# ── pyte SGR → tkinter 颜色 ──────────────────────
# pyte 默认色板 (0-15) + 216 色立方
PYTE_DEFAULT_FG = FG_PRIMARY
PYTE_DEFAULT_BG = BG_DARK

# 标准 16 色
STD_COLORS = {
    0:  BG_DARK,     1:  FG_ACCENT,   2:  FG_GREEN,
    3:  FG_YELLOW,   4:  "#569cd6",   5:  "#c586c0",
    6:  "#4ec9b0",   7:  FG_PRIMARY,
    8:  FG_SECONDARY, 9:  "#f44747",   10: "#6a9955",
    11: "#dcdcaa",   12: "#569cd6",   13: "#c586c0",
    14: "#4ec9b0",   15: "#ffffff",
}


def _pyte_fg_to_tk(fg: str) -> str:
    """pyte 前景色字符串 → tkinter 颜色"""
    if fg == "default":
        return PYTE_DEFAULT_FG
    if fg in STD_COLORS:
        return STD_COLORS[fg]
    # "bold" / "italic" 等非颜色属性
    return PYTE_DEFAULT_FG


def _pyte_bg_to_tk(bg: str) -> str:
    if bg == "default":
        return PYTE_DEFAULT_BG
    if bg in STD_COLORS:
        return STD_COLORS[bg]
    return PYTE_DEFAULT_BG


class TerminalWidget(tk.Canvas):
    """基于 pyte 的终端渲染组件"""

    def __init__(self, parent, cols: int = 100, rows: int = 30, **kw):
        super().__init__(parent, bg=BG_DARK,
                         highlightthickness=0, relief="flat", **kw)

        self.cols = cols
        self.rows = rows

        # pyte 终端
        self.screen = HistoryScreen(cols, rows, history=2000)
        self.stream = pyte.Stream(self.screen)
        self.stream.attach(self.screen)

        # 字体度量
        self._font = tkfont.Font(family="Consolas", size=12)
        self._setup_font_metrics()

        # 输入处理
        self.bind("<Configure>", self._on_resize)
        self.bind("<Key>", self._on_key)

        # 重绘标记
        self._dirty = True
        self._cursor_visible = True

        # 闪烁光标
        self._blink_cursor()

    def _setup_font_metrics(self):
        """计算字符宽高"""
        # 用大写 W 测宽度（最宽字符），高度用 font metrics
        self._char_w = self._font.measure("W")
        self._char_h = self._font.metrics("linespace")
        if self._char_h <= 0:
            self._char_h = 18

    def _on_resize(self, event):
        """窗口大小改变时重算行列数和字符尺寸"""
        self._setup_font_metrics()
        new_cols = max(40, (event.width - 20) // self._char_w)
        new_rows = max(10, (event.height - 16) // self._char_h)
        if new_cols != self.cols or new_rows != self.rows:
            self.cols = new_cols
            self.rows = new_rows
            self.screen = HistoryScreen(new_cols, new_rows,
                                        history=self.screen.history)
            self.stream = pyte.Stream(self.screen)
            self.stream.attach(self.screen)
        self.redraw()

    def write(self, data: str):
        """喂数据给 pyte 解析"""
        self.stream.feed(data)
        self.redraw()

    def redraw(self):
        """标记需要重绘（不立即绘制，等 poll）"""
        self._dirty = True

    def render(self):
        """执行重绘 — 从 pyte screen buffer 读到 Canvas"""
        if not self._dirty:
            return
        self._dirty = False

        self.delete("all")

        x0 = 10
        y0 = 8
        cursor_line = self.screen.cursor.y
        cursor_col = self.screen.cursor.x

        for row_idx in range(self.rows):
            y = y0 + row_idx * self._char_h
            row_data = self.screen.buffer.get(row_idx, {})

            # 按样式分组渲染
            runs = self._style_runs_from_row(row_data, self.cols)
            cx = x0
            for text, fg_color, bg_color, bold in runs:
                if not text:
                    continue
                self.create_text(
                    cx, y,
                    text=text, anchor="nw", fill=fg_color,
                    font=self._font,
                )
                cx += len(text) * self._char_w

        # 光标
        cy = y0 + cursor_line * self._char_h
        cx = x0 + cursor_col * self._char_w
        if self._cursor_visible:
            self.create_rectangle(
                cx, cy, cx + self._char_w, cy + self._char_h,
                fill=FG_PRIMARY, outline="",
                stipple="gray50",
            )

    def _style_runs_from_row(self, row_data: dict, ncols: int):
        """从 pyte buffer 一行中提取 (文本, fg色, bg色, bold) 连续段"""
        runs = []
        cur_text = []
        cur_fg = None
        cur_bg = None
        cur_bold = False

        for col in range(ncols):
            ch = row_data.get(col)
            if ch is None:
                fg, bg, bold = PYTE_DEFAULT_FG, PYTE_DEFAULT_BG, False
                char = " "
            else:
                fg = _pyte_fg_to_tk(ch.fg)
                bg = _pyte_bg_to_tk(ch.bg)
                bold = ch.bold
                char = ch.data

            if fg != cur_fg or bg != cur_bg or bold != cur_bold:
                if cur_text:
                    runs.append(("".join(cur_text), cur_fg or PYTE_DEFAULT_FG,
                                 cur_bg or PYTE_DEFAULT_BG, cur_bold))
                cur_text = []
                cur_fg = fg
                cur_bg = bg
                cur_bold = bold
            cur_text.append(char)

        if cur_text:
            runs.append(("".join(cur_text), cur_fg or PYTE_DEFAULT_FG,
                         cur_bg or PYTE_DEFAULT_BG, cur_bold))
        return runs

    def _on_key(self, event):
        """键盘事件 → 回调"""
        if hasattr(self, "_key_callback") and self._key_callback:
            self._key_callback(event)

    def _blink_cursor(self):
        self._cursor_visible = not self._cursor_visible
        self.redraw()
        self.after(530, self._blink_cursor)


class WalTerminal:
    """暗色终端窗口 — pyte + subprocess"""

    def __init__(self, root: tk.Tk, project: str, mode: str = "writing",
                 model: str = "deepseek-chat"):
        self.root = root
        self.project = project
        self.mode = mode
        self.model = model

        self.root.title(f"WAL — {project} [{mode}]")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("960x640")
        self.root.minsize(600, 400)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        # ── 菜单 ──
        menubar = tk.Menu(root, bg=BG_MID, fg=FG_PRIMARY,
                          activebackground=BG_INPUT, activeforeground=FG_PRIMARY,
                          relief="flat", bd=0)
        root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0, bg=BG_MID, fg=FG_PRIMARY,
                            activebackground=BG_INPUT, activeforeground=FG_PRIMARY)
        file_menu.add_command(label="重启 REPL", command=self.restart)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit)
        menubar.add_cascade(label="WAL", menu=file_menu)

        # ── 终端画布 ──
        self.terminal = TerminalWidget(root, cols=100, rows=30)
        self.terminal.grid(row=0, column=0, sticky="nsew", padx=(4, 4), pady=(4, 0))
        self.terminal._key_callback = self._on_term_key

        # 滚动条
        scrollbar = tk.Scrollbar(root, bg=BG_MID, troughcolor=BG_DARK,
                                 activebackground=BG_INPUT, relief="flat",
                                 command=self._on_scroll)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=(4, 0))

        # ── 输入行 ──
        input_frame = tk.Frame(root, bg=BG_MID)
        input_frame.grid(row=1, column=0, columnspan=2, sticky="ew",
                         padx=6, pady=(4, 6))
        input_frame.columnconfigure(1, weight=1)

        tk.Label(input_frame, text="▸", bg=BG_MID, fg=FG_ACCENT,
                 font=FONT_BOLD).grid(row=0, column=0, padx=(10, 4))

        self.input_entry = tk.Entry(
            input_frame,
            bg=BG_MID, fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            font=FONT_NORMAL,
            relief="flat", borderwidth=0,
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=6)
        self.input_entry.bind("<Return>", self._on_enter)
        self.input_entry.bind("<Up>", self._history_up)
        self.input_entry.bind("<Down>", self._history_down)

        # ── 进程 ──
        self.process: subprocess.Popen | None = None
        self.reader_thread: threading.Thread | None = None
        self.output_queue: queue.Queue = queue.Queue()
        self.running = False
        self.history: list[str] = []
        self.history_idx = -1

        self._start_repl()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(50, self._poll_output)

    # ── 进程 ──────────────────────────────────────

    def _start_repl(self):
        venv = os.environ.get("WAL_VENV", "d:/PyVenv/WAL")
        python = os.path.join(venv, "Scripts", "python.exe")
        cwd = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))

        cmd = [python, "-m", "wal.agent.launch",
               self.project, "--mode", self.mode, "--model", self.model]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        self.process = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1,
        )
        self.running = True
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()
        self.root.title(f"WAL — {self.project} [{self.mode}]")

    def _read_output(self):
        try:
            while self.running and self.process and self.process.stdout:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.output_queue.put(("out", line))
        except (ValueError, OSError):
            pass
        finally:
            if self.running:
                self.output_queue.put(("exit", ""))

    def _poll_output(self):
        try:
            while True:
                kind, text = self.output_queue.get_nowait()
                if kind == "out":
                    # 喂给 pyte 终端 → Canvas 渲染
                    self.terminal.write(text)
                elif kind == "exit":
                    self.terminal.write("\n[进程已退出 — 可通过菜单重启]\n")
                    self.running = False
        except queue.Empty:
            pass
        # 每次 poll 都渲染一次
        self.terminal.render()
        if self.running:
            self.root.after(30, self._poll_output)

    def _send(self, text: str):
        if self.process and self.process.stdin and self.running:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
                # 也显示在终端上
                self.terminal.write(f"> {text}\n")
                if text.strip():
                    self.history.append(text.strip())
                self.history_idx = len(self.history)
            except (BrokenPipeError, OSError):
                self.terminal.write("\n[无法发送输入，进程已关闭]\n")

    # ── 输入 ──────────────────────────────────────

    def _on_enter(self, event):
        text = self.input_entry.get()
        self.input_entry.delete(0, "end")
        self._send(text)
        return "break"

    def _history_up(self, event):
        if self.history and self.history_idx > 0:
            self.history_idx -= 1
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, self.history[self.history_idx])
        return "break"

    def _history_down(self, event):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, self.history[self.history_idx])
        else:
            self.history_idx = len(self.history)
            self.input_entry.delete(0, "end")
        return "break"

    def _on_term_key(self, event):
        """Canvas 上的键盘事件 — 转发到输入框"""
        self.input_entry.focus_set()
        if event.char and event.char.isprintable():
            self.input_entry.insert(tk.INSERT, event.char)
        elif event.keysym == "BackSpace":
            pos = self.input_entry.index(tk.INSERT)
            if pos > 0:
                self.input_entry.delete(pos - 1)
        elif event.keysym == "Return":
            self._on_enter(None)

    def _on_scroll(self, *args):
        """滚动条 — 调整 pyte screen 可见区域"""
        # 简化处理：滚动条控制历史回溯
        pass

    # ── 控制 ──────────────────────────────────────

    def restart(self):
        self.terminal.write("\n[正在重启...]\n")
        self._kill_process()
        self.output_queue = queue.Queue()
        self._start_repl()

    def _kill_process(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                self.process.kill()

    def quit(self):
        self._kill_process()
        self.root.destroy()
