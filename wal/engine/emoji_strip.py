"""终端 Emoji 兼容 — 当终端不支持 Unicode Emoji 时，替换为纯 ASCII 标记

通过环境变量 WAL_NO_EMOJI=1 触发。start.ps1 会自动检测终端能力并设置。
"""

import os
import re

# Emoji → ASCII 映射表
EMOJI_MAP = {
    "⚠️": "[!!]",        # ⚠️ Warning
    "⚡": "[>>]",              # ⚡ Zap / 重要
    "\U0001f512": "[锁]",          # 🔒 Lock / 约束
    "⭐": "[*]",               # ⭐ Star / 重要
    "\U0001f4cb": "[计]",          # 📋 Clipboard / 规划
    "✍️": "[写]",        # ✍️ Writing
    "✅": "[OK]",              # ✅ Check
    "→": "->",                # → Arrow
    "—": "--",                # — Em Dash
    "★": "*",                 # ★ Star
    "\U0001f525": "[火]",          # 🔥 Fire
    "\U0001f4a1": "[思]",          # 💡 Idea
    "\U0001f3af": "[靶]",          # 🎯 Target
    "\U0001f50d": "[搜]",          # 🔍 Search
}


def strip_emoji(text: str) -> str:
    """将文本中的 Emoji 替换为 ASCII 等价标记"""
    result = text
    for emoji, ascii_replacement in EMOJI_MAP.items():
        result = result.replace(emoji, ascii_replacement)
    return result


def should_strip_emoji() -> bool:
    """检查是否需要去除 Emoji"""
    return os.environ.get("WAL_NO_EMOJI", "").strip() == "1"
