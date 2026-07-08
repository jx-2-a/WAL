# Autonomous Tools (自主模式工具)

13 个自主写作控制工具。

## 控制工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `set_autonomy_level` | level | 设置自主等级：suggest_only / auto_minor / auto_moderate / full_auto |
| `set_direction` | direction | 设置写作方向指令 |
| `start_auto_session` | [chapter, target_words] | 开始自主写作会话 |
| `end_auto_session` | [summary] | 结束会话 |
| `get_auto_status` | — | 获取当前自主状态 |

## 检查点

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_checkpoint` | [label] | 创建检查点 |
| `rollback_to_checkpoint` | checkpoint_id | 回滚到检查点 |
| `list_checkpoints` | — | 列出所有检查点 |

## 决策审批

| 工具 | 参数 | 说明 |
|------|------|------|
| `approve_decision` | decision_id | 批准自主决策 |
| `reject_decision` | decision_id, [reason] | 拒绝决策 |

## 其他

| 工具 | 参数 | 说明 |
|------|------|------|
| `switch_mode` | mode | 切换模式 |
| 记忆工具 | — | 同 shared/memory |
