#!/usr/bin/env python3
"""WAL GUI 启动器 — 暗色终端窗口

用法:
    python wal_gui.py                  # 弹窗选项目
    python wal_gui.py <project>        # 直接启动
    python wal_gui.py <project> --mode planning
"""

from wal.gui.__main__ import main

if __name__ == "__main__":
    main()
