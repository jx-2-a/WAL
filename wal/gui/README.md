# GUI — 暗色桌面终端窗口

免终端启动 WAL REPL，tkinter 实现，零额外依赖。

## 文件结构

```
gui/
├── __init__.py      # 公开 API
├── __main__.py      # python -m wal.gui 入口
├── theme.py         # 颜色、字体、主题常量
├── selector.py      # ProjectSelector — 项目选择弹窗
├── terminal.py      # WalTerminal — 暗色终端窗口 + REPL 子进程
└── README.md
```

## 启动方式

```powershell
# 弹窗选择项目
python -m wal.gui

# 直接启动指定项目
python -m wal.gui <project_name>
python -m wal.gui <project_name> --mode planning
```

或双击根目录 `wal_gui.py`。

## 功能

- 深蓝黑配色（`#1a1a2e` 背景）
- 自动扫描 `projects/` 目录，弹窗选择
- 菜单栏切换 writing / planning / autonomous 模式
- ↑↓ 命令历史
- 重启 / 退出

## 依赖

- Python 标准库：tkinter, subprocess, threading, queue, pathlib
- 零外部依赖
