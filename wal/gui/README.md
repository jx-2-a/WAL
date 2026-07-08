# GUI — 项目选择器 + 终端启动

tkinter 弹窗选择项目，选完后在 **Windows Terminal**（或 PowerShell）中运行 `start.ps1`。

效果和 VS Code 终端完全一致。

## 文件

```
gui/
├── __init__.py      # 公开 API
├── __main__.py      # python -m wal.gui 入口
├── theme.py         # 颜色/字体
├── selector.py      # 项目选择弹窗 + 终端启动逻辑
└── README.md
```

## 启动

```powershell
python -m wal.gui                    # 弹窗选项目
python -m wal.gui 青石               # 直接启动指定项目
python -m wal.gui 青石 --mode planning
```

## 流程

1. 弹窗显示项目列表（编号选择 / 输入名字创建）
2. 选择模式和项目
3. 在 Windows Terminal（或回退 PowerShell）中执行 `start.ps1`
4. 弹窗关闭，终端接管一切
