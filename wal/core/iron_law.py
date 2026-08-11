"""铁律引擎 — 剧情设定红线扫描，防跑偏

铁律 = 可配置的「剧情规则表」。每条铁律含一组关键词，并声明关键词的合法范围：

- `only_in_volume`：关键词**只允许**出现在指定卷（如「万山之祖传承」只允许出现在卷五）。
  0 表示不限。
- `forbidden_volumes`：关键词**禁止**出现在这些卷（卷号列表）。

写正文时对内容做关键词扫描，命中且落在禁止范围即报违规。这是防跑偏的
事后兜底（P2）——把「铁律靠 LLM 自觉」变成「代码层扫描」。
"""

import json
from pathlib import Path
from typing import Optional

from ..storage.connection import Database
from ..storage.base import DatabaseRepository


class IronLawRepository(DatabaseRepository):
    """iron_laws 表的数据仓库"""

    def save(self, law: dict) -> None:
        self._insert_or_replace("iron_laws", {
            "id": law["id"],
            "name": law.get("name", ""),
            "keywords": self._to_json(law.get("keywords", [])),
            "forbidden_volumes": self._to_json(law.get("forbidden_volumes", [])),
            "only_in_volume": int(law.get("only_in_volume", 0) or 0),
            "severity": law.get("severity", "warning"),
            "note": law.get("note", ""),
        })

    def load_all(self) -> list[dict]:
        rows = self._fetch_all("SELECT * FROM iron_laws ORDER BY only_in_volume, id")
        result = []
        for r in rows:
            r["keywords"] = self._from_json(r["keywords"])
            r["forbidden_volumes"] = self._from_json(r["forbidden_volumes"])
            result.append(r)
        return result

    def load(self, law_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM iron_laws WHERE id = ?", (law_id,))
        if not row:
            return None
        row["keywords"] = self._from_json(row["keywords"])
        row["forbidden_volumes"] = self._from_json(row["forbidden_volumes"])
        return row

    def delete(self, law_id: str) -> bool:
        return self._delete("iron_laws", "id = ?", (law_id,)) > 0

    def next_id(self) -> int:
        return self._count("iron_laws") + 1


class IronLawManager:
    """铁律引擎管理器"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        db_path = self.project_dir / "wal.db"
        self.db = Database(str(db_path))
        self.repo = IronLawRepository(self.db)
        if not self.db.schema_exists():
            self.db.init_schema()

    # ═══ CRUD ═══════════════════════════════════════════════════

    def add_iron_law(self, name: str, keywords: list[str] | None = None,
                     forbidden_volumes: list[int] | None = None,
                     only_in_volume: int = 0,
                     severity: str = "warning", note: str = "") -> dict:
        """新增一条铁律"""
        law_id = f"law_{self.repo.next_id():03d}"
        law = {
            "id": law_id,
            "name": name,
            "keywords": [str(k).strip() for k in (keywords or []) if str(k).strip()],
            "forbidden_volumes": [int(v) for v in (forbidden_volumes or []) if str(v).strip().lstrip("-").isdigit()],
            "only_in_volume": int(only_in_volume or 0),
            "severity": severity if severity in ("warning", "block") else "warning",
            "note": note,
        }
        self.repo.save(law)
        return law

    def list_iron_laws(self) -> list[dict]:
        """列出全部铁律"""
        return self.repo.load_all()

    def get_iron_law(self, law_id: str) -> Optional[dict]:
        return self.repo.load(law_id)

    def delete_iron_law(self, law_id: str) -> dict:
        if self.repo.delete(law_id):
            return {"deleted": True, "law_id": law_id}
        return {"error": f"铁律 {law_id} 不存在"}

    # ═══ 扫描 ═══════════════════════════════════════════════════

    def scan_text(self, text: str, volume_number: int = 0) -> list[dict]:
        """扫描一段文本，返回违规列表

        Args:
            text: 要扫描的正文
            volume_number: 当前卷号。0 表示未知卷（此时只检查 only_in_volume 且
                目标卷明确的命中——若文本出现在别卷即违规；forbidden 判断需卷号）

        Returns:
            list[dict]: 每条含 law_id/law_name/keyword/reason/severity
        """
        if not text:
            return []
        violations = []
        for law in self.repo.load_all():
            kw_hits = [kw for kw in law["keywords"] if kw and kw in text]
            if not kw_hits:
                continue
            only_in = int(law.get("only_in_volume") or 0)
            forb = law.get("forbidden_volumes") or []
            for kw in kw_hits:
                reasons = []
                if only_in > 0 and volume_number > 0 and volume_number != only_in:
                    reasons.append(f"铁律「{law['name']}」的关键词『{kw}』只允许出现在第{only_in}卷")
                if only_in > 0 and volume_number == 0:
                    reasons.append(f"铁律「{law['name']}」的关键词『{kw}』只能出现在第{only_in}卷，请确认当前卷号")
                if volume_number > 0 and volume_number in forb:
                    reasons.append(f"铁律「{law['name']}」的关键词『{kw}』禁止出现在第{volume_number}卷")
                for reason in reasons:
                    violations.append({
                        "law_id": law["id"],
                        "law_name": law["name"],
                        "keyword": kw,
                        "reason": reason,
                        "severity": law.get("severity", "warning"),
                        "note": law.get("note", ""),
                    })
        return violations

    def scan_chapter(self, chapter_number: int, content: str = "") -> list[dict]:
        """扫描某一章正文，返回违规列表

        若未传入 content，则从 StoryManager 读取该章全部场景正文。

        Args:
            chapter_number: 章节号
            content: 可选，直接传入要扫描的正文（避免重复读取）

        Returns:
            list[dict]: 违规列表；违规条目的 `volume_number` 字段标注当前卷
        """
        # 确定当前卷号
        volume_number = 0
        try:
            from .story import StoryManager
            sm = StoryManager(str(self.project_dir))
            sm.load_story()
            ch = sm.get_chapter(chapter_number)
            if ch:
                vid = getattr(ch, "volume_id", "") or ""
                if vid:
                    vol_row = sm.repo.load_volume(vid)
                    if vol_row:
                        volume_number = int(vol_row.get("number") or 0)
        except Exception:
            volume_number = 0

        if not content:
            try:
                from .story import StoryManager
                sm = StoryManager(str(self.project_dir))
                sm.load_story()
                ch = sm.get_chapter(chapter_number)
                if ch:
                    content = "\n".join(sc.content for sc in ch.scenes if sc.content.strip())
            except Exception:
                content = ""

        violations = self.scan_text(content, volume_number)
        for v in violations:
            v["chapter_number"] = chapter_number
            v["volume_number"] = volume_number
        return violations
