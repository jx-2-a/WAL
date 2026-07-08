"""python -m wal.gui 入口 — 仿 start.ps1 交互流"""

import sys
import os
import argparse
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from wal.gui.selector import ProjectSelector
from wal.gui.terminal import WalTerminal


def _init_dpi():
    """Windows 高 DPI 适配"""
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _scan_projects() -> list[str]:
    base = Path(os.environ.get("WAL_PROJECTS", "projects"))
    if not base.exists():
        return []
    return sorted([
        d.name for d in base.iterdir()
        if d.is_dir() and (d / "wal.db").exists()
    ])


def main():
    _init_dpi()

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

    # ── 无项目 → 始终弹选择窗 ──
    if not project:
        projects = _scan_projects()

        if not projects:
            # 零项目 → 直接创建
            root = tk.Tk()
            root.withdraw()
            name = messagebox.askstring(
                "创建项目", "没有找到项目。\n\n输入新项目名称:",
                parent=root,
            )
            root.destroy()
            if not name:
                sys.exit(0)
            project = name
        else:
            # 有项目 → 弹选择窗
            root = tk.Tk()
            selector = ProjectSelector(root, projects)
            root.mainloop()  # 选择器会调用 root.quit() 退出

            project = selector.result
            if not project:
                sys.exit(0)
            mode = selector.mode
            root.destroy()

            # mode 已在选择器中设置
            if mode and mode != args.mode:
                args.mode = mode

    # ── 启动终端 ──
    root = tk.Tk()
    WalTerminal(root, project, mode=args.mode, model=args.model)
    root.mainloop()


if __name__ == "__main__":
    main()
