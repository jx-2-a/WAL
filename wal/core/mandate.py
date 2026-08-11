"""写作指令构建器 — 防跑偏的核心「硬性输入」

把散落各处的防跑偏信息聚合为一份「写作指令」：

- 当前卷 + 章节范围锁
- 铁律（IronLawManager）
- 必读设定文档（自定义文档，按 `agent_config['auto_mandatory_docs']` 顺序）
- 当前章骨架锚点

这份指令同时用于两条路径：
1. `get_writing_mandate` 工具 —— LLM 主动获取
2. AgentLoop 进入自主模式时**自动注入系统提示词** —— 代码层保证，不靠提示词自觉
"""

import json
import re
from pathlib import Path
from typing import Optional

from ..storage.connection import Database
from .story import StoryManager
from .iron_law import IronLawManager


class MandateBuilder:
    """写作指令构建器"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(str(self.project_dir / "wal.db"))
        self.db.init_schema()

    # ═══ agent_config 读写 ═══════════════════════════════════════

    def get_config(self, key: str, default: str = "") -> str:
        with self.db.get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM agent_config WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default

    def set_config(self, key: str, value: str) -> None:
        with self.db.get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agent_config (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    # ═══ 自定义文档读取 ═══════════════════════════════════════════

    def _read_custom_doc(self, doc_id: str) -> Optional[dict]:
        with self.db.get_conn() as conn:
            row = conn.execute(
                "SELECT id, title, category, content FROM custom_documents "
                "WHERE id = ? AND story_id = 'main'", (doc_id,)
            ).fetchone()
            return dict(row) if row else None

    def _find_docs_by_title_fragment(self, fragment: str) -> list[dict]:
        with self.db.get_conn() as conn:
            rows = conn.execute(
                "SELECT id, title, category, content FROM custom_documents "
                "WHERE story_id = 'main' AND title LIKE ? ORDER BY updated_at DESC",
                (f"%{fragment}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    # ═══ 骨架锚点提取 ═════════════════════════════════════════════

    def extract_chapter_anchor(self, skeleton_text: str,
                               chapter_number: int) -> str:
        """从骨架正文中提取「第N章」的锚点内容

        支持格式：`第50章 孤霞岭` / `50章 孤霞岭` / `50 孤霞岭` / `50、孤霞岭`
        """
        if not skeleton_text:
            return ""
        patterns = [
            re.compile(rf"第\s*{chapter_number}\s*章[：:、\s]*([^\n]{{1,200}})"),
            re.compile(rf"^\s*{chapter_number}\s*章[：:、\s]*([^\n]{{1,200}})", re.M),
            re.compile(rf"^\s*[\[（(]?\s*{chapter_number}\s*[\]）)]?\s*[.、．.\s]+([^\n]{{1,200}})", re.M),
        ]
        for pat in patterns:
            m = pat.search(skeleton_text)
            if m:
                anchor = m.group(1).strip().strip("*")
                if anchor:
                    return anchor[:200]
        return ""

    # ═══ 卷定位 ═══════════════════════════════════════════════════

    def _resolve_volume(self, sm: StoryManager, volume_number: int = 0,
                        current_chapter: int = 0) -> Optional[dict]:
        """确定当前卷。优先级：参数 > 配置 > 当前章反推"""
        vol_rows = sm.repo.list_volumes()

        if volume_number:
            for v in vol_rows:
                if int(v["number"]) == int(volume_number):
                    return v
            return None

        if current_chapter:
            # 按卷范围反推
            for v in vol_rows:
                start = int(v.get("chapter_start") or 0)
                end = int(v.get("chapter_end") or 0)
                if start > 0 and end > 0 and start <= current_chapter <= end:
                    return v
            # 按章节 volume_id 反推
            ch = sm.get_chapter(current_chapter)
            if ch and getattr(ch, "volume_id", ""):
                return sm.repo.load_volume(ch.volume_id)

        # 配置
        cfg = self.get_config("auto_current_volume", "")
        if cfg and cfg.isdigit():
            for v in vol_rows:
                if int(v["number"]) == int(cfg):
                    return v
        return None

    # ═══ 组装 ═════════════════════════════════════════════════════

    def build(self, volume_number: int = 0,
              current_chapter: int = 0) -> dict:
        """组装写作指令 dict"""
        sm = StoryManager(str(self.project_dir))
        sm.load_story()

        vol = self._resolve_volume(sm, volume_number, current_chapter)

        # 卷信息
        volume_info = None
        if vol:
            ch_rows = sm.repo.list_chapters(volume_id=vol["id"])
            done = sum(1 for c in ch_rows if c.get("status") == "done")
            volume_info = {
                "volume_id": vol["id"],
                "number": vol["number"],
                "title": vol["title"],
                "theme": vol.get("theme", ""),
                "status": vol.get("status", ""),
                "chapter_start": vol.get("chapter_start") or 0,
                "chapter_end": vol.get("chapter_end") or 0,
                "chapter_count": len(ch_rows),
                "done_chapters": done,
            }

        # 铁律
        im = IronLawManager(str(self.project_dir))
        laws = im.list_iron_laws()

        # 必读文档
        docs = self._load_mandatory_docs(vol["number"] if vol else 0)

        # 骨架锚点
        skeleton_text = "\n\n".join(d.get("content", "") for d in docs
                                    if "骨架" in d.get("title", "")
                                    or "规划" in d.get("title", "")
                                    or "执行" in d.get("title", ""))
        anchor = ""
        chapter_info = None
        if current_chapter:
            ch = sm.get_chapter(current_chapter)
            if ch:
                anchor = getattr(ch, "anchor", "") or ch.summary or ""
                if skeleton_text and not anchor:
                    anchor = self.extract_chapter_anchor(skeleton_text, current_chapter)
                chapter_info = {
                    "number": current_chapter,
                    "title": ch.title,
                    "anchor": anchor or "",
                    "status": ch.status,
                    "word_count": ch.actual_word_count,
                    "target_words": ch.word_count_target,
                }

        # 范围锁状态
        range_lock = {
            "current_volume": vol["number"] if vol else 0,
            "chapter_start": volume_info["chapter_start"] if volume_info else 0,
            "chapter_end": volume_info["chapter_end"] if volume_info else 0,
            "locked": bool(vol and (volume_info["chapter_start"] and volume_info["chapter_end"])),
        }

        return {
            "volume": volume_info,
            "range_lock": range_lock,
            "iron_laws": laws,
            "mandatory_docs": docs,
            "chapter": chapter_info,
        }

    def _load_mandatory_docs(self, volume_number: int) -> list[dict]:
        """按配置顺序读取必读文档；未配置时按标题模式兜底"""
        cfg = self.get_config("auto_mandatory_docs", "")
        docs: list[dict] = []
        seen: set[str] = set()

        def _add(doc: dict):
            if doc and doc["id"] not in seen:
                seen.add(doc["id"])
                docs.append(doc)

        if cfg:
            try:
                ids = json.loads(cfg)
                for doc_id in ids:
                    _add(self._read_custom_doc(str(doc_id)))
            except (json.JSONDecodeError, TypeError):
                pass
        else:
            # 兜底：核心设定速查 + 当前卷执行骨架 + 五卷规划
            for d in self._find_docs_by_title_fragment("核心设定速查"):
                _add(d)
            if volume_number:
                for d in self._find_docs_by_title_fragment(f"第{volume_number}卷执行骨架"):
                    _add(d)
            for d in self._find_docs_by_title_fragment("执行骨架"):
                _add(d)
            for d in self._find_docs_by_title_fragment("五卷完整规划"):
                _add(d)
            for d in self._find_docs_by_title_fragment("五卷规划"):
                _add(d)
        return docs

    # ═══ 格式化 ═══════════════════════════════════════════════════

    def format(self, mandate: dict, doc_cap: int = 3000,
               total_doc_cap: int = 9000) -> str:
        """把 mandate dict 格式化为可读文本"""
        lines: list[str] = []
        vol = mandate.get("volume") or {}
        rl = mandate.get("range_lock") or {}
        chapter = mandate.get("chapter") or {}

        # 卷 + 范围锁
        lines.append("📌 当前卷")
        if vol:
            lines.append(f"  第{vol.get('number','?')}卷《{vol.get('title','')}》"
                         f" 状态：{vol.get('status','')}")
            if vol.get("theme"):
                lines.append(f"  主题：{vol['theme']}")
            if vol.get("chapter_start") and vol.get("chapter_end"):
                lines.append(
                    f"  🚧 章节范围锁：第{vol['chapter_start']}~{vol['chapter_end']}章"
                    f"（已写 {vol.get('done_chapters',0)}/{vol.get('chapter_count',0)} 章）"
                    f"——超出范围必须显式 set_current_volume 确认进入下一卷")
        else:
            lines.append("  未定位当前卷。请先用 set_current_volume(卷号) 声明。")

        # 铁律
        laws = mandate.get("iron_laws") or []
        if laws:
            lines.append("⛔ 铁律（写正文时命中即违规）")
            for law in laws:
                kw = "、".join(law.get("keywords", []))
                scope = f"只允许在第{law['only_in_volume']}卷" if law.get("only_in_volume") else "全卷可用"
                forb = f"；禁止卷：{'、'.join(f'第{v}卷' for v in law.get('forbidden_volumes', []))}" if law.get("forbidden_volumes") else ""
                lines.append(f"  - 【{law.get('name','')}】关键词：{kw}（{scope}{forb}）")
                if law.get("note"):
                    lines.append(f"    说明：{law['note']}")
        else:
            lines.append("⛔ 铁律：暂未配置（可用 add_iron_law 添加）")

        # 本章锚点
        if chapter:
            lines.append("📄 本章写作锚点")
            lines.append(f"  第{chapter.get('number','?')}章《{chapter.get('title','')}》"
                         f"（{chapter.get('status','')}，{chapter.get('word_count',0)}/"
                         f"{chapter.get('target_words',0)}字）")
            if chapter.get("anchor"):
                lines.append(f"  锚点：{chapter['anchor']}")
            else:
                lines.append("  锚点：未设置（可用 set_chapter_anchor 补充）")

        # 必读文档
        docs = mandate.get("mandatory_docs") or []
        if docs:
            lines.append("📄 必读设定文档（写作前必读，来自自定义文档）")
            remaining = total_doc_cap
            for d in docs:
                content = (d.get("content") or "").strip()
                if len(content) > doc_cap:
                    content = content[:doc_cap] + f"\n…（截断，共{len(d.get('content') or '')}字）"
                if len(content) > remaining:
                    content = content[:remaining] + "\n…（已到指令总长上限）"
                remaining -= len(content)
                lines.append(f"\n—— 【{d.get('title','')}】——\n{content}")
                if remaining <= 0:
                    break

        return "\n".join(lines)
