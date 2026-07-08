"""项目选择窗口 — 仿 start.ps1 交互流"""

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


class ProjectSelector:
    """启动时选择 WAL 项目 — 编号选择 + 输入名字创建"""

    def __init__(self, parent: tk.Tk, projects: list[str]):
        self.parent = parent
        self.result: str | None = None
        self.projects = projects
        self.mode = "writing"  # 默认模式

        parent.title("WAL — 选择项目")
        parent.configure(bg=BG_DARK)
        parent.geometry("520x440")
        parent.minsize(420, 320)

        # 居中
        parent.update_idletasks()
        w, h = 520, 440
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        parent.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()

        # 聚焦输入框
        self.input_entry.focus_set()

    # ── UI ─────────────────────────────────────────

    def _build_ui(self):
        parent = self.parent

        # 清空已有内容（如果有）
        for w in parent.winfo_children():
            w.destroy()

        # 标题
        tk.Label(
            parent, text="WAL 1.0 — 小说写作 Agent",
            bg=BG_DARK, fg=FG_GREEN,
            font=FONT_BOLD_14,
        ).pack(pady=(20, 5))

        # ── 项目列表 ──
        list_frame = tk.Frame(parent, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, padx=30, pady=(10, 0))

        tk.Label(
            list_frame, text="已有项目:", bg=BG_DARK, fg=FG_SECONDARY,
            font=FONT_SMALL,
        ).pack(anchor="w")

        list_inner = tk.Frame(list_frame, bg=BG_MID)
        list_inner.pack(fill="both", expand=True, pady=(4, 0))

        self.listbox = tk.Listbox(
            list_inner,
            bg=BG_MID, fg=FG_PRIMARY,
            selectbackground=BG_INPUT, selectforeground=FG_PRIMARY,
            font=FONT_NORMAL,
            relief="flat", borderwidth=0,
            activestyle="none",
            highlightthickness=0,
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        scrollbar = tk.Scrollbar(list_inner, bg=BG_MID, troughcolor=BG_MID,
                                 activebackground=BG_INPUT, relief="flat")
        scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=8)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)

        # 绑定
        self.listbox.bind("<Double-Button-1>", lambda e: self._select_by_number())
        self.listbox.bind("<Return>", lambda e: self._select_by_number())
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

        for p in self.projects:
            self.listbox.insert("end", f"  {p}")
        if self.projects:
            self.listbox.selection_set(0)

        # ── 输入区 ──
        input_frame = tk.Frame(parent, bg=BG_DARK)
        input_frame.pack(fill="x", padx=30, pady=(12, 0))

        tk.Label(
            input_frame, text="输入编号选择, 或输入名字创建新项目:", bg=BG_DARK,
            fg=FG_SECONDARY, font=FONT_SMALL,
        ).pack(anchor="w")

        entry_frame = tk.Frame(parent, bg=BG_DARK)
        entry_frame.pack(fill="x", padx=30, pady=(4, 12))

        self.input_entry = tk.Entry(
            entry_frame,
            bg=BG_MID, fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            font=FONT_NORMAL,
            relief="flat", borderwidth=0,
        )
        self.input_entry.pack(fill="x", ipady=6, padx=8)
        self.input_entry.bind("<Return>", self._on_enter)

        # ── 按钮行 ──
        btn_frame = tk.Frame(parent, bg=BG_DARK)
        btn_frame.pack(fill="x", padx=30, pady=(0, 8))

        # 模式选择（writing / planning / autonomous）
        mode_frame = tk.Frame(btn_frame, bg=BG_DARK)
        mode_frame.pack(side="left")
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
            ).pack(side="left", padx=(8, 0))

        # 按钮
        self.launch_btn = tk.Button(
            btn_frame, text="启动", command=self._select_by_number,
            bg=BG_INPUT, fg=FG_GREEN,
            activebackground=BG_MID, activeforeground=FG_GREEN,
            font=FONT_SMALL,
            relief="flat", borderwidth=0, padx=20, pady=4,
            cursor="hand2",
        )
        self.launch_btn.pack(side="right", padx=(8, 0))
        tk.Button(
            btn_frame, text="取消", command=self._quit,
            bg=BG_MID, fg=FG_ACCENT,
            activebackground=BG_INPUT, activeforeground=FG_ACCENT,
            font=FONT_SMALL,
            relief="flat", borderwidth=0, padx=16, pady=4,
            cursor="hand2",
        ).pack(side="right")

        # 提示
        tk.Label(
            parent, text="项目存放在 projects/ 目录下，每个项目一个文件夹",
            bg=BG_DARK, fg=FG_SECONDARY,
            font=(FONT_FAMILY, 9),
        ).pack(pady=(0, 12))

    # ── 事件 ──────────────────────────────────────

    def _on_list_select(self, event):
        """列表选中时同步到输入框"""
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, str(idx + 1))

    def _on_enter(self, event):
        self._submit()

    def _select_by_number(self):
        """从列表选中项启动"""
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            self.result = self.projects[idx]
            self.mode = self.mode_var.get()
            self.parent.quit()

    def _submit(self):
        """处理输入：数字=选择项目，文字=创建新项目"""
        text = self.input_entry.get().strip()
        if not text:
            # 空输入 → 用列表选中项
            self._select_by_number()
            return

        # 数字 → 选择对应编号的项目
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(self.projects):
                self.result = self.projects[idx]
                self.mode = self.mode_var.get()
                self.parent.quit()
                return
            else:
                messagebox.showwarning("无效编号",
                                       f"请输入 1-{len(self.projects)} 之间的编号",
                                       parent=self.parent)
                return

        # 文字 → 创建新项目或使用已有项目名
        name = text
        if name in self.projects:
            self.result = name
            self.mode = self.mode_var.get()
            self.parent.quit()
            return

        # 确认创建
        if messagebox.askyesno(
            "创建新项目",
            f"创建新项目 '{name}'?\n\n将使用默认设置创建。",
            parent=self.parent,
        ):
            ok = self._create_project(name)
            if ok:
                self.result = name
                self.mode = self.mode_var.get()
                self.parent.quit()
            else:
                messagebox.showerror("创建失败", f"无法创建项目 '{name}'",
                                     parent=self.parent)

    def _create_project(self, name: str) -> bool:
        """调用 CLI 创建新项目"""
        venv = os.environ.get("WAL_VENV", "d:/PyVenv/WAL")
        python = os.path.join(venv, "Scripts", "python.exe")
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            r = subprocess.run(
                [python, "-m", "wal.cli.main", "init", name,
                 "--author", "佚名", "--summary", "新故事", "--genre", "General"],
                cwd=script_dir, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=30,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _quit(self):
        self.result = None
        self.parent.quit()
