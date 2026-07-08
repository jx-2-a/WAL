"""WAL 暗色终端窗口 — 内嵌 REPL 进程"""

import os
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import font

from wal.gui.theme import (
    BG_DARK, BG_MID, BG_INPUT,
    FG_PRIMARY, FG_SECONDARY, FG_ACCENT, FG_GREEN, FG_YELLOW,
    FONT_FAMILY, FONT_SIZE, FONT_BOLD_14, FONT_NORMAL, FONT_BOLD, FONT_SMALL,
)


class WalTerminal:
    """暗色终端包装器 — 内嵌 WAL REPL 子进程"""

    def __init__(self, root: tk.Tk, project: str, mode: str = "writing",
                 model: str = "deepseek-chat"):
        self.root = root
        self.project = project
        self.mode = mode
        self.model = model

        self.root.title(f"WAL 1.0 — {project} [{mode}]")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("960x640")
        self.root.minsize(600, 400)

        # 响应式
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        # ── 菜单 ──
        self._build_menu()

        # ── 输出区 ──
        text_frame = tk.Frame(root, bg=BG_DARK)
        text_frame.grid(row=0, column=0, sticky="nsew", padx=(8, 8), pady=(8, 0))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.output = tk.Text(
            text_frame,
            bg=BG_DARK, fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            selectbackground=BG_INPUT, selectforeground=FG_PRIMARY,
            font=FONT_NORMAL,
            wrap="word", state="disabled",
            relief="flat", borderwidth=0,
            padx=10, pady=10,
        )
        self.output.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, bg=BG_MID, troughcolor=BG_DARK,
                                 activebackground=BG_INPUT, relief="flat")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.output.yview)

        # ── 输入行 ──
        input_frame = tk.Frame(root, bg=BG_MID)
        input_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 8))
        input_frame.columnconfigure(1, weight=1)

        tk.Label(
            input_frame, text="▸", bg=BG_MID, fg=FG_ACCENT,
            font=FONT_BOLD,
        ).grid(row=0, column=0, padx=(10, 4))

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

        # ── 启动 ──
        self._start_repl()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(50, self._poll_output)

    # ── 菜单 ──────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self.root, bg=BG_MID, fg=FG_PRIMARY,
                          activebackground=BG_INPUT, activeforeground=FG_PRIMARY,
                          relief="flat", bd=0)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg=BG_MID, fg=FG_PRIMARY,
                            activebackground=BG_INPUT, activeforeground=FG_PRIMARY)
        file_menu.add_command(label="重启 REPL", command=self.restart)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit)
        menubar.add_cascade(label="WAL", menu=file_menu)

        mode_menu = tk.Menu(menubar, tearoff=0, bg=BG_MID, fg=FG_PRIMARY,
                            activebackground=BG_INPUT, activeforeground=FG_PRIMARY)
        for m in ("writing", "planning", "autonomous"):
            label = f"◆ {m}" if m == self.mode else f"  {m}"
            mode_menu.add_command(label=label,
                                  command=lambda m=m: self._switch_mode(m))
        menubar.add_cascade(label="模式", menu=mode_menu)

    # ── 进程管理 ──────────────────────────────────

    def _start_repl(self):
        venv = os.environ.get("WAL_VENV", "d:/PyVenv/WAL")
        python = os.path.join(venv, "Scripts", "python.exe")
        cwd = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))

        cmd = [python, "-m", "wal.agent.launch",
               self.project, "--mode", self.mode, "--model", self.model]
        self._append(f"[系统] 启动: {' '.join(cmd)}\n", FG_GREEN)

        self.process = subprocess.Popen(
            cmd, cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1,
        )
        self.running = True
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()
        self.root.title(f"WAL 1.0 — {self.project} [{self.mode}]")

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
                    self._append(text)
                elif kind == "exit":
                    self._append("\n[系统] 进程已退出 — 可通过菜单重启\n", FG_ACCENT)
                    self.running = False
        except queue.Empty:
            pass
        if self.running:
            self.root.after(30, self._poll_output)

    def _send(self, text: str):
        if self.process and self.process.stdin and self.running:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
                self._append(f"{text}\n", FG_SECONDARY)
                if text.strip():
                    self.history.append(text.strip())
                self.history_idx = len(self.history)
            except (BrokenPipeError, OSError):
                self._append("[系统] 无法发送输入，进程已关闭\n", FG_ACCENT)

    # ── 输出 ──────────────────────────────────────

    def _append(self, text: str, color: str = FG_PRIMARY):
        self.output.config(state="normal")
        tag = f"c_{color.replace('#', '')}"
        self.output.tag_config(tag, foreground=color)
        self.output.insert("end", text, tag)
        self.output.see("end")
        self.output.config(state="disabled")

    # ── 输入事件 ──────────────────────────────────

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

    # ── 控制 ──────────────────────────────────────

    def _switch_mode(self, mode: str):
        if mode == self.mode:
            return
        self.mode = mode
        self._append(f"\n[系统] 切换到 {mode} 模式...\n", FG_YELLOW)
        self._kill_process()
        self.output_queue = queue.Queue()
        self._start_repl()

    def restart(self):
        self._append("\n[系统] 正在重启...\n", FG_YELLOW)
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
