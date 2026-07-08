"""python -m wal.gui 入口"""

import sys
import os
import argparse
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from wal.gui.selector import ProjectSelector
from wal.gui.terminal import WalTerminal
from wal.gui.theme import BG_DARK


def _scan_projects() -> list[str]:
    base = Path(os.environ.get("WAL_PROJECTS", "projects"))
    if not base.exists():
        return []
    return sorted([
        d.name for d in base.iterdir()
        if d.is_dir() and (d / "wal.db").exists()
    ])


def main():
    parser = argparse.ArgumentParser(
        description="WAL 暗色终端窗口",
        prog="python -m wal.gui",
    )
    parser.add_argument("project", nargs="?",
                        help="项目名称（不指定则弹窗选择）")
    parser.add_argument("--mode", default="writing",
                        choices=["writing", "planning", "autonomous"])
    parser.add_argument("--model", default="deepseek-chat")
    args, unknown = parser.parse_known_args()

    project = args.project

    # ── 无项目 → 先选 ──
    if not project:
        projects = _scan_projects()
        if not projects:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "错误",
                "未找到项目。\n"
                "请在 projects/ 目录下创建项目，或指定项目名：\n"
                "  python -m wal.gui <project_name>"
            )
            root.destroy()
            sys.exit(1)

        # 只有一个项目 → 直接启动
        if len(projects) == 1:
            project = projects[0]
            root = tk.Tk()
        else:
            root = tk.Tk()
            root.geometry("400x300+100+100")
            root.title("WAL")
            root.configure(bg=BG_DARK)
            root.update()

            selector = ProjectSelector(root, projects)
            root.wait_window(selector)
            project = selector.result
            if not project:
                root.destroy()
                sys.exit(0)

            for w in root.winfo_children():
                w.destroy()
    else:
        root = tk.Tk()

    WalTerminal(root, project, mode=args.mode, model=args.model)
    root.mainloop()


if __name__ == "__main__":
    main()
