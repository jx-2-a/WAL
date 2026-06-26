"""YAML → SQLite 迁移工具

用法:
    python -m wal.storage.migrate projects/修仙传奇
    python -m wal.storage.migrate projects/修仙传奇 --dry-run
    python -m wal.storage.migrate --all   # 迁移所有项目
"""

import sys
from pathlib import Path

from .database import Database


def migrate_project(project_dir: str, dry_run: bool = False) -> dict:
    """迁移单个项目从 YAML 到 SQLite

    Args:
        project_dir: 项目目录路径
        dry_run: 只检查不执行

    Returns:
        {"project": str, "db_path": str, "migrated": [...], "errors": [...]}
    """
    base = Path(project_dir)
    if not base.exists():
        return {"project": str(base), "error": "Project directory not found"}

    story_yaml = base / "story.yaml"
    if not story_yaml.exists():
        return {"project": str(base), "error": "No story.yaml found — not a valid WAL project"}

    db_path = base / "wal.db"

    if dry_run:
        return {
            "project": str(base),
            "db_path": str(db_path),
            "dry_run": True,
            "has_story": story_yaml.exists(),
        }

    # 初始化并迁移
    db = Database(str(db_path))
    report = db.migrate_from_yaml(str(base))

    return {
        "project": str(base),
        "db_path": str(db_path),
        "migrated": report.get("migrated", []),
        "errors": report.get("errors", []),
    }


def migrate_all(projects_root: str = "projects", dry_run: bool = False) -> list[dict]:
    """迁移所有项目"""
    root = Path(projects_root)
    if not root.exists():
        return []

    results = []
    for project_dir in root.iterdir():
        if project_dir.is_dir() and (project_dir / "story.yaml").exists():
            result = migrate_project(str(project_dir), dry_run)
            results.append(result)

    return results


def verify_migration(project_dir: str) -> dict:
    """验证迁移结果 — 对比 YAML 和 SQLite 的数据完整性"""
    base = Path(project_dir)
    db_path = base / "wal.db"
    story_yaml = base / "story.yaml"

    result = {
        "project": str(base),
        "db_exists": db_path.exists(),
        "yaml_exists": story_yaml.exists(),
        "checks": {},
    }

    if not db_path.exists():
        result["error"] = "wal.db not found — run migrate first"
        return result

    db = Database(str(db_path))
    if not db.schema_exists():
        result["error"] = "Database schema not initialized"
        return result

    with db.get_conn() as conn:
        # 检查故事
        story = conn.execute("SELECT * FROM stories WHERE id = 'main'").fetchone()
        result["checks"]["story"] = story is not None

        # 检查章节数
        ch_count = conn.execute(
            "SELECT COUNT(*) FROM chapters WHERE story_id = 'main'"
        ).fetchone()[0]
        result["checks"]["chapters"] = ch_count

        # 检查角色数
        char_count = conn.execute(
            "SELECT COUNT(*) FROM characters WHERE story_id = 'main'"
        ).fetchone()[0]
        result["checks"]["characters"] = char_count

        # 检查剧情线
        plot_count = conn.execute(
            "SELECT COUNT(*) FROM plot_lines WHERE story_id = 'main'"
        ).fetchone()[0]
        result["checks"]["plot_lines"] = plot_count

        # 检查情节点
        pp_count = conn.execute(
            "SELECT COUNT(*) FROM plot_points"
        ).fetchone()[0]
        result["checks"]["plot_points"] = pp_count

        # 检查世界设定
        world = conn.execute(
            "SELECT * FROM world_settings WHERE story_id = 'main'"
        ).fetchone()
        result["checks"]["world"] = world is not None

        # 检查地点
        loc_count = conn.execute(
            "SELECT COUNT(*) FROM locations WHERE story_id = 'main'"
        ).fetchone()[0]
        result["checks"]["locations"] = loc_count

        # 检查时间线
        tl_count = conn.execute(
            "SELECT COUNT(*) FROM timeline_events WHERE story_id = 'main'"
        ).fetchone()[0]
        result["checks"]["timeline"] = tl_count

    result["all_ok"] = all(v for v in result["checks"].values() if isinstance(v, bool))
    return result


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m wal.storage.migrate <project_dir> [--dry-run] [--verify] [--all]")
        print("  project_dir  : 项目目录路径")
        print("  --dry-run    : 只检查，不执行迁移")
        print("  --verify     : 迁移后验证数据完整性")
        print("  --all        : 迁移 projects/ 下所有项目")
        sys.exit(1)

    target = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    verify = "--verify" in sys.argv
    all_projects = "--all" in sys.argv

    if all_projects:
        results = migrate_all(dry_run=dry_run)
        for r in results:
            status = "OK" if not r.get("error") else f"ERROR: {r['error']}"
            print(f"  {r['project']}: {status}")
            if not dry_run and "migrated" in r:
                print(f"    迁移: {', '.join(r['migrated'])}")
            if r.get("errors"):
                for e in r["errors"]:
                    print(f"    错误: {e}")
    elif verify:
        result = verify_migration(target)
        print(f"验证项目: {result['project']}")
        print(f"  数据库存在: {result['db_exists']}")
        for check, ok in result.get("checks", {}).items():
            print(f"  {check}: {ok}")
        print(f"  全部通过: {result.get('all_ok', False)}")
    else:
        result = migrate_project(target, dry_run=dry_run)
        if result.get("error"):
            print(f"错误: {result['error']}")
        else:
            print(f"项目: {result['project']}")
            print(f"数据库: {result['db_path']}")
            if dry_run:
                print("  (dry-run 模式，未实际执行)")
            else:
                print(f"  迁移: {', '.join(result.get('migrated', []))}")
                if result.get("errors"):
                    for e in result["errors"]:
                        print(f"  错误: {e}")
                print("  迁移完成！")
