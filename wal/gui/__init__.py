"""WAL GUI — 项目选择器 + 终端启动

用法:
    python -m wal.gui                  # 弹窗选项目
    python -m wal.gui <project>        # 直接启动
    python -m wal.gui <project> --mode planning
"""

from wal.gui.selector import ProjectSelector, launch_in_terminal
