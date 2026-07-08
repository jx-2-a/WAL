"""python -m wal.gui 入口"""

import sys
import os
import argparse
import tkinter as tk
from pathlib import Path

from wal.gui.selector import ProjectSelector, launch_in_terminal


def _init_dpi():
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
        description="WAL 启动器", prog="python -m wal.gui")
    parser.add_argument("project", nargs="?",
                        help="项目名称（不指定则弹窗选择）")
    parser.add_argument("--mode", default="writing",
                        choices=["writing", "planning", "autonomous"])
    parser.add_argument("--model", default="deepseek-chat")
    args, unknown = parser.parse_known_args()

    if args.project:
        # 直接启动
        launch_in_terminal(args.project, mode=args.mode, model=args.model)
        sys.exit(0)

    # 弹窗选择
    projects = _scan_projects()

    root = tk.Tk()
    root.withdraw()

    if not projects:
        from tkinter import messagebox
        name = messagebox.askstring(
            "创建项目", "没有找到项目。\n\n输入新项目名称:", parent=root)
        if not name:
            sys.exit(0)
    else:
        selector = ProjectSelector(root, projects)
        root.wait_window(selector)
        name = selector.result
        if not name:
            sys.exit(0)

    root.destroy()


if __name__ == "__main__":
    main()
