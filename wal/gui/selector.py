"""项目选择弹窗 — 选完即关闭，启动终端"""

import os
import subprocess
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from wal.gui.theme import (
    BG_DARK, BG_MID, BG_INPUT,
    FG_PRIMARY, FG_SECONDARY, FG_ACCENT, FG_GREEN, FG_YELLOW,
    FONT_FAMILY, FONT_BOLD_14, FONT_NORMAL, FONT_SMALL,
)

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _find_terminal() -> str | None:
    """探测可用的终端模拟器，优先 Windows Terminal"""
    # Windows Terminal (Win10 1903+)
    wt = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe")
    if os.path.exists(wt):
        return wt
    # 系统 PATH 中的 wt
    if subprocess.run(["where", "wt"], capture_output=True, shell=True).returncode == 0:
        return "wt"
    return None


def launch_in_terminal(project: str, mode: str = "writing",
                       model: str = "deepseek-chat") -> None:
    """在 Windows Terminal / PowerShell 中启动 start.ps1"""
    start_ps1 = os.path.join(SCRIPT_DIR, "start.ps1")

    mode_arg = "-Mode" if mode != "writing" else ""
    mode_val = mode if mode != "writing" else ""

    cmd = f"& '{start_ps1}' '{project}' {mode_arg} {mode_val}"
    cmd = cmd.strip()

    wt = _find_terminal()
    if wt:
        # Windows Terminal: wt -d <cwd> powershell -NoExit -Command "..."
        subprocess.Popen(
            [wt, "-d", SCRIPT_DIR, "powershell", "-NoExit", "-Command", cmd],
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    else:
        # 回退 PowerShell
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command",
             f"cd '{SCRIPT_DIR}'; {cmd}"],
        )


class ProjectSelector(tk.Toplevel):
    """选择项目 + 模式，确认后启动终端并关闭"""

    def __init__(self, parent: tk.Tk, projects: list[str]):
        super().__init__(parent)
        self.result: str | None = None
        self.mode = "writing"

        self.title("WAL — 选择项目")
        self.configure(bg=BG_DARK)
        self.geometry("480x400")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._center(parent)

        # 标题
        tk.Label(
            self, text="WAL 1.0 — 小说写作 Agent",
            bg=BG_DARK, fg=FG_GREEN, font=FONT_BOLD_14,
        ).pack(pady=(20, 10))

        # 项目列表
        list_frame = tk.Frame(self, bg=BG_MID)
        list_frame.pack(fill="both", expand=True, padx=30, pady=(0, 10))

        self.listbox = tk.Listbox(
            list_frame,
            bg=BG_MID, fg=FG_PRIMARY,
            selectbackground=BG_INPUT, selectforeground=FG_PRIMARY,
            font=FONT_NORMAL,
            relief="flat", borderwidth=0,
            activestyle="none", highlightthickness=0,
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        self.listbox.bind("<Double-Button-1>", lambda e: self._launch_selected())
        self.listbox.bind("<Return>", lambda e: self._launch_selected())

        for i, p in enumerate(projects, 1):
            self.listbox.insert("end", f"  {i}. {p}")
        if projects:
            self.listbox.selection_set(0)

        # 输入行
        tk.Label(
            self, text="输入编号选择, 或输入名字创建新项目:",
            bg=BG_DARK, fg=FG_SECONDARY, font=FONT_SMALL,
        ).pack(anchor="w", padx=30)

        entry_frame = tk.Frame(self, bg=BG_DARK)
        entry_frame.pack(fill="x", padx=30, pady=(4, 8))

        self.input_entry = tk.Entry(
            entry_frame,
            bg=BG_MID, fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            font=FONT_NORMAL,
            relief="flat", borderwidth=0,
        )
        self.input_entry.pack(fill="x", ipady=6, padx=8)
        self.input_entry.bind("<Return>", lambda e: self._submit())
        self.input_entry.focus_set()

        # 模式
        mode_frame = tk.Frame(self, bg=BG_DARK)
        mode_frame.pack(fill="x", padx=30, pady=(0, 4))
        tk.Label(mode_frame, text="模式:", bg=BG_DARK, fg=FG_SECONDARY,
                 font=FONT_SMALL).pack(side="left")
        self.mode_var = tk.StringVar(value="writing")
        for m in ("writing", "planning", "autonomous"):
            tk.Radiobutton(
                mode_frame, text=m, variable=self.mode_var, value=m,
                bg=BG_DARK, fg=FG_SECONDARY,
                selectcolor=BG_MID,
                activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                font=FONT_SMALL, relief="flat",
            ).pack(side="left", padx=(10, 0))

        # 按钮
        btn_frame = tk.Frame(self, bg=BG_DARK)
        btn_frame.pack(fill="x", padx=30, pady=(4, 20))
        tk.Button(
            btn_frame, text="启动终端", command=self._launch_selected,
            bg=BG_INPUT, fg=FG_GREEN,
            activebackground=BG_MID, activeforeground=FG_GREEN,
            font=FONT_SMALL,
            relief="flat", borderwidth=0, padx=20, pady=4,
            cursor="hand2",
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            btn_frame, text="取消", command=self.destroy,
            bg=BG_MID, fg=FG_ACCENT,
            activebackground=BG_INPUT, activeforeground=FG_ACCENT,
            font=FONT_SMALL,
            relief="flat", borderwidth=0, padx=16, pady=4,
            cursor="hand2",
        ).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ── 逻辑 ─────────────────────────────────────

    def _center(self, parent: tk.Tk):
        self.update_idletasks()
        w, h = 480, 400
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _launch_selected(self):
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            if idx < len(self.listbox.get(0, "end")):
                # 提取名字（去掉编号前缀）
                text = self.listbox.get(idx).strip()
                # 格式: "1. 项目名"
                parts = text.split(". ", 1)
                name = parts[1] if len(parts) > 1 else text
                self._launch(name)

    def _submit(self):
        text = self.input_entry.get().strip()
        if not text:
            self._launch_selected()
            return

        if text.isdigit():
            idx = int(text) - 1
            items = self.listbox.get(0, "end")
            if 0 <= idx < len(items):
                parts = items[idx].strip().split(". ", 1)
                name = parts[1] if len(parts) > 1 else items[idx].strip()
                self._launch(name)
                return
            else:
                messagebox.showwarning("无效编号", f"请输入 1-{len(items)}",
                                       parent=self)
                return

        # 文字 → 项目名
        self._launch(text)

    def _launch(self, project: str):
        mode = self.mode_var.get()
        self.result = project
        self.mode = mode
        launch_in_terminal(project, mode)
        self.destroy()
