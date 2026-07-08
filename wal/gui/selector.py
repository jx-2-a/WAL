"""项目选择弹窗"""

import tkinter as tk
from tkinter import font
from wal.gui.theme import (
    BG_DARK, BG_MID, BG_INPUT,
    FG_PRIMARY, FG_ACCENT, FG_GREEN,
    FONT_FAMILY, FONT_SIZE, FONT_BOLD_14, FONT_NORMAL,
)


class ProjectSelector(tk.Toplevel):
    """启动时选择 WAL 项目的暗色弹窗"""

    def __init__(self, parent: tk.Tk, projects: list[str]):
        super().__init__(parent)
        self.result: str | None = None

        self.title("选择项目 — WAL")
        self.configure(bg=BG_DARK)
        self.geometry("400x280")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._center(parent)

        # 标题
        tk.Label(
            self, text="选择小说项目", bg=BG_DARK, fg=FG_PRIMARY,
            font=FONT_BOLD_14,
        ).pack(pady=(20, 10))

        # 项目列表
        list_frame = tk.Frame(self, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, padx=20)

        self.listbox = tk.Listbox(
            list_frame,
            bg=BG_MID, fg=FG_PRIMARY,
            selectbackground=BG_INPUT, selectforeground=FG_PRIMARY,
            font=FONT_NORMAL,
            relief="flat", borderwidth=0,
            activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self._select())
        self.listbox.bind("<Return>", lambda e: self._select())

        for p in projects:
            self.listbox.insert("end", p)
        if projects:
            self.listbox.selection_set(0)

        # 按钮
        btn_frame = tk.Frame(self, bg=BG_DARK)
        btn_frame.pack(pady=(10, 20))
        self._btn(btn_frame, "启动", self._select, FG_GREEN).pack(side="left", padx=4)
        self._btn(btn_frame, "取消", self.destroy, FG_ACCENT).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ── 内部 ──────────────────────────────────────

    def _center(self, parent: tk.Tk):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 400, 280
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _btn(self, parent, text, cmd, color):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=BG_INPUT, fg=color,
            activebackground=BG_MID, activeforeground=color,
            font=font.Font(family=FONT_FAMILY, size=10),
            relief="flat", borderwidth=0, padx=16, pady=4,
            cursor="hand2",
        )

    def _select(self):
        sel = self.listbox.curselection()
        if sel:
            self.result = self.listbox.get(sel[0])
        self.destroy()
