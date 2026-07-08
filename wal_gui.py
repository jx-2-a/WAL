#!/usr/bin/env python3
"""WAL 启动器 — 选择项目 → 在 Windows Terminal 中启动

用法:
    python wal_gui.py                  # 弹窗选项目
    python wal_gui.py 青石             # 直接启动
    python wal_gui.py 青石 --mode planning
"""

from wal.gui.__main__ import main

if __name__ == "__main__":
    main()
