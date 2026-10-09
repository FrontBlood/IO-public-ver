from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_BACKUP_ROOT = Path(
    os.getenv(
        "DB_BACKUP_ROOT",
        str((Path("E:/") / "数据库备档") if os.name == "nt" else (PROJECT_ROOT / "db_backups")),
    )
)
DATABASE_BACKUP_RETENTION_DAYS = int(os.getenv("DB_BACKUP_RETENTION_DAYS", "30"))
DATABASE_BACKUP_MAX_COPIES = int(os.getenv("DB_BACKUP_MAX_COPIES", "60"))


def _backup_sqlite_database(source: Path, destination: Path) -> str:
    try:
        with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
        return "sqlite_backup"
    except sqlite3.DatabaseError:
        shutil.copy2(source, destination)
        return "file_copy"


def backup_project_databases(
    backup_root: Path = DATABASE_BACKUP_ROOT,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(project_root),
        "backup_dir": str(backup_dir),
        "databases": [],
    }

    for source in sorted(project_root.glob("*.db")):
        destination = backup_dir / source.name
        method = _backup_sqlite_database(source, destination)
        manifest["databases"].append(
            {
                "name": source.name,
                "source": str(source),
                "backup": str(destination),
                "bytes": source.stat().st_size,
                "method": method,
            }
        )

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    prune_database_backups(backup_root)
    return backup_dir


def _parse_backup_timestamp(path: Path) -> datetime | None:
    try:
        return datetime.strptime(path.name, "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def prune_database_backups(
    backup_root: Path = DATABASE_BACKUP_ROOT,
    *,
    retention_days: int = DATABASE_BACKUP_RETENTION_DAYS,
    max_copies: int = DATABASE_BACKUP_MAX_COPIES,
) -> list[Path]:
    if not backup_root.exists():
        return []

    backups: list[tuple[datetime, Path]] = []
    for child in backup_root.iterdir():
        if not child.is_dir():
            continue
        created_at = _parse_backup_timestamp(child)
        if created_at is not None:
            backups.append((created_at, child))

    backups.sort(key=lambda item: item[0], reverse=True)
    cutoff = datetime.now() - timedelta(days=max(0, retention_days))
    to_delete: set[Path] = set()

    if retention_days > 0:
        to_delete.update(path for created_at, path in backups if created_at < cutoff)

    if max_copies > 0:
        to_delete.update(path for _created_at, path in backups[max_copies:])

    deleted: list[Path] = []
    for path in sorted(to_delete):
        shutil.rmtree(path)
        deleted.append(path)

    if deleted:
        print(
            "[DatabaseBackup] Pruned old backups: "
            + ", ".join(str(path) for path in deleted)
        )
    return deleted
