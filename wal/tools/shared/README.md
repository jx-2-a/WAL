# Shared Tools (共享工具)

3 个跨模式记忆工具，所有模式可用。

## 工具列表

| 工具 | 参数 | 说明 |
|------|------|------|
| `save_agent_memory` | project_name, key, value | 保存 key-value 记忆 |
| `get_agent_memory` | project_name, [key] | 读取记忆（key 为空列出所有） |
| `delete_agent_memory` | project_name, key | 删除记忆 |

记忆存储在 SQLite `agent_config` 表中（key 加 `mem_` 前缀），重启后依然存在。
