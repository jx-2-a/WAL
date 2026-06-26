"""上下文窗口管理器 — 滑动窗口 + 摘要压缩 + RAG 检索注入

百万字级核心：不解决上下文管理，Agent 几轮对话就撑爆 128K 窗口。

策略：
  1. 保留 system prompt（固定）
  2. 保留最近 window_rounds 轮完整对话
  3. 更早的消息 → 压缩为摘要
  4. 工具结果截断（超长内容裁剪）
  5. 可选：根据用户查询从 FTS5 检索相关上下文注入
"""

from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# Token 估算器
# ═══════════════════════════════════════════════════════════════

class TokenCounter:
    """DeepSeek token 估算器（近似，无需 API 调用）

    基于字符统计的启发式估算：
      - CJK 字符：~1.5 字符/token
      - ASCII/拉丁字符：~4 字符/token
      - 精度约 ±10%，足够用于窗口管理决策

    DeepSeek V3/R1 实际 tokenizer 行为类似，此估算器误差在可接受范围。
    """

    def count(self, text: str) -> int:
        """估算文本的 token 数"""
        if not text:
            return 0
        cjk_chars = 0
        other_chars = 0
        for ch in text:
            code = ord(ch)
            if (0x4E00 <= code <= 0x9FFF or      # CJK Unified
                0x3400 <= code <= 0x4DBF or      # CJK Extension A
                0x20000 <= code <= 0x2A6DF or    # CJK Extension B
                0xF900 <= code <= 0xFAFF or      # CJK Compatibility
                0x3040 <= code <= 0x309F or      # Hiragana
                0x30A0 <= code <= 0x30FF or      # Katakana
                0xAC00 <= code <= 0xD7AF):       # Hangul
                cjk_chars += 1
            else:
                other_chars += 1
        # CJK: ~1.5 chars/token, Other: ~4 chars/token
        return max(1, int(cjk_chars / 1.5 + other_chars / 4))

    def count_messages(self, messages: list[dict]) -> int:
        """估算整个消息列表的 token 数"""
        total = 0
        for msg in messages:
            total += self._count_message(msg)
        return total

    def _count_message(self, msg: dict) -> int:
        """估算单条消息的 token 数"""
        tokens = 4  # 消息格式开销 (~4 tokens)
        if msg.get("content"):
            tokens += self.count(str(msg["content"]))
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                tokens += self.count(str(func.get("name", "")))
                tokens += self.count(str(func.get("arguments", "")))
        if msg.get("role") == "tool":
            tokens += self.count(str(msg.get("content", "")))
        return tokens


# ═══════════════════════════════════════════════════════════════
# 工具结果截断
# ═══════════════════════════════════════════════════════════════

def truncate_tool_result(result: str, max_chars: int = 2000,
                         max_list_items: int = 20,
                         scene_content_max: int = 500) -> str:
    """智能截断工具返回结果，防止撑爆上下文

    策略：
      - 纯文本：保留前 1500 字符 + 尾部摘要
      - 列表（JSON 数组）：保留前 20 条 + 总数说明
      - 场景正文（超长 content 字段）：仅保留前 500 字符 + 统计

    返回截断后的字符串。
    """
    if len(result) <= max_chars:
        return result

    import json

    # 尝试解析为 JSON
    try:
        data = json.loads(result)
        return _truncate_json(data, max_list_items, scene_content_max)
    except (json.JSONDecodeError, TypeError):
        pass

    # 纯文本截断
    head = result[:1500]
    tail = result[-300:] if len(result) > 1800 else ""
    return (
        f"{head}\n\n... (内容过长，已截断。完整长度：{len(result)} 字符) ...\n\n"
        + (f"... (尾部) ...\n{tail}" if tail else "")
    )


def _truncate_json(data, max_list_items: int, scene_content_max: int) -> str:
    """截断 JSON 数据"""
    import json

    if isinstance(data, list):
        total = len(data)
        if total > max_list_items:
            truncated = data[:max_list_items]
            result = json.dumps(truncated, ensure_ascii=False, indent=2)
            return f"{result}\n\n... (共 {total} 条，仅显示前 {max_list_items} 条。用 search_story_index 检索更多)"
        return json.dumps(data, ensure_ascii=False, indent=2)

    if isinstance(data, dict):
        # 截断超长字段
        truncated = {}
        for k, v in data.items():
            if isinstance(v, str) and len(v) > scene_content_max:
                truncated[k] = (
                    v[:scene_content_max]
                    + f"... (截断，完整长度 {len(v)} 字符)"
                )
            elif isinstance(v, list) and len(v) > max_list_items:
                truncated[k] = v[:max_list_items] + [f"... 共 {len(v)} 项"]
            elif isinstance(v, dict):
                truncated[k] = _truncate_dict_values(v, scene_content_max)
            else:
                truncated[k] = v
        return json.dumps(truncated, ensure_ascii=False, indent=2)

    return json.dumps(data, ensure_ascii=False, indent=2)


def _truncate_dict_values(d: dict, max_len: int) -> dict:
    """递归截断字典中的超长字符串"""
    result = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > max_len:
            result[k] = v[:max_len] + f"... (截断，{len(v)}字符)"
        elif isinstance(v, dict):
            result[k] = _truncate_dict_values(v, max_len)
        else:
            result[k] = v
    return result


# ═══════════════════════════════════════════════════════════════
# 上下文窗口管理器
# ═══════════════════════════════════════════════════════════════

class ContextManager:
    """Agent 上下文窗口管理器

    核心策略：滑动窗口 + 压缩旧消息为摘要 + RAG 检索注入

    使用方式：
        cm = ContextManager(max_tokens=90000, window_rounds=6)
        messages = cm.manage(messages)  # 在每轮 LLM 调用前
        messages = cm.inject_retrieved_context(messages, user_query, project_dir)
    """

    def __init__(self, max_tokens: int = 90000, window_rounds: int = 12):
        """
        Args:
            max_tokens: 上下文窗口总 token 预算（默认 90K，DeepSeek 128K 留余量）
            window_rounds: 保留的最近完整对话轮数（默认 12，从旧默认 6 扩大）
        """
        self.max_tokens = max_tokens
        self.window_rounds = window_rounds
        self.counter = TokenCounter()
        self._running_summary = ""  # 累积摘要（压缩的旧消息）
        self._summary_tokens = 0

    def manage(self, messages: list[dict]) -> list[dict]:
        """主入口：保证消息列表在 max_tokens 预算内

        步骤：
          1. 分离 system prompt（第 0 条，永远保留）
          2. 标记最近 window_rounds 轮（保留完整）
          3. 压缩更早的消息 → 合并到 running_summary
          4. 如果仍超限 → 压缩 running_summary

        Returns:
            管理后的消息列表
        """
        if not messages:
            return messages

        # 1. System prompt 始终保留
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # 2. 找出最近 N 轮（一轮 = user → assistant + tools ... 直到下个 user）
        recent = self._extract_recent_rounds(non_system, self.window_rounds)
        old = [m for m in non_system if m not in recent]

        # 3. 压缩旧消息
        if old:
            new_summary = self._compress_messages(old)
            if new_summary:
                self._running_summary = self._merge_summaries(
                    self._running_summary, new_summary
                )
                self._summary_tokens = self.counter.count(self._running_summary)

        # 4. 组装最终消息列表
        managed = list(system_msgs)

        # 注入累积摘要
        if self._running_summary:
            managed.append({
                "role": "system",
                "content": f"[对话历史摘要]\n{self._running_summary}",
            })

        managed.extend(recent)

        # 5. 如果仍超限，压缩摘要
        total_tokens = self.counter.count_messages(managed)
        while total_tokens > self.max_tokens and self._running_summary:
            self._running_summary = self._compress_summary(self._running_summary)
            self._summary_tokens = self.counter.count(self._running_summary)
            # 重建
            managed = list(system_msgs)
            if self._running_summary:
                managed.append({
                    "role": "system",
                    "content": f"[对话历史摘要]\n{self._running_summary}",
                })
            managed.extend(recent)
            total_tokens = self.counter.count_messages(managed)

        return managed

    def inject_retrieved_context(self, messages: list[dict],
                                  user_query: str,
                                  project_dir: str) -> list[dict]:
        """根据用户查询，从 SQLite/FTS5 检索相关上下文并注入

        用于 RAG 增强：在 system prompt 后插入检索到的相关片段。
        """
        if not user_query:
            return messages

        try:
            from ..core.index_manager import IndexManager
            im = IndexManager(project_dir)
            results = im.search(user_query, limit=5)
            if not results:
                return messages

            ctx_lines = ["\n## 检索到的相关上下文（来自全文搜索）\n"]
            for r in results[:5]:
                snippet = r.get("snippet", "")
                snippet_text = snippet.replace("<b>", "").replace("</b>", "")
                ch_title = r.get("chapter_title", "")
                scene_title = r.get("scene_title", "")
                ctx_lines.append(
                    f"- [{ch_title}] {scene_title}: {snippet_text[:150]}"
                )

            context_block = "\n".join(ctx_lines)

            # 插入到 system prompt 之后
            new_messages = []
            system_inserted = False
            for msg in messages:
                new_messages.append(msg)
                if msg.get("role") == "system" and not system_inserted:
                    new_messages.append({
                        "role": "system",
                        "content": context_block,
                    })
                    system_inserted = True

            return new_messages
        except Exception:
            return messages  # RAG 失败不影响主流程

    def reset(self) -> None:
        """重置累积摘要"""
        self._running_summary = ""
        self._summary_tokens = 0

    # ═══ 内部方法 ═══════════════════════════════════════════════

    def _extract_recent_rounds(self, messages: list[dict],
                                rounds: int) -> list[dict]:
        """提取最近 N 轮对话（一轮以 user 消息为界）"""
        if not messages:
            return []
        # 从后往前找 user 消息
        user_indices = []
        for i, m in enumerate(messages):
            if m.get("role") == "user":
                user_indices.append(i)
        if not user_indices:
            # 没有 user 消息，保留所有
            return list(messages)
        # 取最后 N 个 user 消息的起始位置
        start_idx = user_indices[-min(rounds, len(user_indices))]
        return messages[start_idx:]

    def _compress_messages(self, messages: list[dict]) -> str:
        """将旧消息压缩为一段摘要（启发式，无需 LLM）

        提取关键信息：
          - 用户的问题/指令
          - 工具调用的名称和结果摘要
          - 对话主题变化
        """
        if not messages:
            return ""

        lines = []
        last_role = None

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                # 用户消息：保留核心指令（前 200 字符）
                text = str(content).strip()
                if text:
                    lines.append(f"- 用户：{text[:200]}")

            elif role == "assistant":
                # Assistant 消息
                if msg.get("tool_calls"):
                    tools_used = []
                    for tc in msg["tool_calls"]:
                        func = tc.get("function", {})
                        tools_used.append(func.get("name", "?"))
                    if tools_used:
                        lines.append(f"- Agent 调用了工具：{', '.join(tools_used)}")
                elif content:
                    text = str(content).strip()
                    if text:
                        lines.append(f"- Agent：{text[:150]}")

            elif role == "tool":
                # 工具结果：只保留摘要
                text = str(content).strip()
                if len(text) > 200:
                    text = text[:200] + "..."
                lines.append(f"  → {text[:200]}")

        if not lines:
            return ""

        return "以下为早期对话摘要：\n" + "\n".join(lines[-50:])  # 最多保留 50 行摘要

    def _merge_summaries(self, existing: str, new: str) -> str:
        """合并累积摘要与新摘要"""
        if not existing:
            return new
        if not new:
            return existing
        # 简单拼接，控制总长度
        combined = existing + "\n\n---\n\n" + new
        if len(combined) > 4000:
            combined = existing[-2000:] + "\n\n---\n\n" + new
        return combined

    def _compress_summary(self, summary: str) -> str:
        """进一步压缩摘要（去掉细节，保留事件标题）"""
        if not summary:
            return ""
        # 保留前 1/3 + 后 1/3
        lines = summary.split("\n")
        if len(lines) <= 30:
            return summary[:len(summary)//2] + "\n... (已压缩) ..."
        keep = len(lines) // 3
        head = "\n".join(lines[:keep])
        tail = "\n".join(lines[-keep:])
        return head + f"\n... (省略 {len(lines) - 2*keep} 行历史) ...\n" + tail


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════

def estimate_tokens(text: str) -> int:
    """估算文本的 token 数"""
    return TokenCounter().count(text)


def estimate_message_tokens(messages: list[dict]) -> int:
    """估算消息列表的 token 数"""
    return TokenCounter().count_messages(messages)
