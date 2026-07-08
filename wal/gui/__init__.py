"""WAL GUI — 暗色桌面终端窗口

用法:
    python -m wal.gui                  # 弹窗选项目
    python -m wal.gui <project>        # 直接启动
    python -m wal.gui <project> --mode planning
"""

from wal.gui.terminal import WalTerminal
from wal.gui.selector import ProjectSelector
