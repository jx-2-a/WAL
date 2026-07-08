# WAL 工具系统

## 架构

```
AgentLoop (agent/loop.py)
  │
  ├─ Writing mode  ──→ wal.tools.writing  (TOOL_DEFINITIONS, execute_tool)
  ├─ Planning mode ──→ wal.tools.planning  (PLAN_TOOL_DEFINITIONS, execute_plan_tool)
  ├─ Autonomous mode → wal.tools.autonomous (AUTO_TOOL_DEFINITIONS, execute_auto_tool)
  └─ All modes ──────→ wal.tools.web       (WEB_TOOL_DEFINITIONS, execute_web_tool)
                      → wal.tools.shared    (memory tools)
```

## 工具分组

| 组 | 目录 | 工具数 | 说明 |
|----|------|--------|------|
| Writing | `writing/` | ~52 | 故事/角色/剧情/导出全功能 |
| Planning | `planning/` | 14 | 剧情分析/头脑风暴/规划笔记 |
| Autonomous | `autonomous/` | 13 | 自主写作控制/检查点 |
| Web | `web/` | 4 | 搜索/抓取/百科 |
| Shared | `shared/` | 3 | 跨模式持久记忆 |

## 如何添加新工具

1. 在对应 `schemas.py` 中添加 JSON schema
2. 在 `implementations.py` 中实现函数
3. 在 `dispatch.py` 的 `tool_map` 中添加 lambda
4. 更新 `__init__.py` 的 `__all__`

## 向后兼容

旧路径仍可用（通过 shim 重定向）：

```python
# 旧路径（已弃用，但可用）
from wal.agent.tool_defs import TOOL_DEFINITIONS, execute_tool

# 新路径（推荐）
from wal.tools.writing import TOOL_DEFINITIONS, execute_tool
from wal.tools import TOOL_DEFINITIONS  # 顶层快捷方式
```
