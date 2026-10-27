import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", "/var/lib/bloom/meijia.db"))
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/var/lib/bloom/uploads"))
BACKUP_ROOT = Path(os.environ.get("BACKUP_ROOT", "/var/backups/bloom"))
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Database does not exist: {DATABASE_PATH}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = BACKUP_ROOT / timestamp
    destination.mkdir(parents=True, exist_ok=False)

    database_backup = destination / "meijia.db"
    source = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
    target = sqlite3.connect(database_backup)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    uploads_archive = Path(shutil.make_archive(
        str(destination / "uploads"),
        "gztar",
        root_dir=MEDIA_ROOT,
    ))
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "database": {"bytes": database_backup.stat().st_size, "sha256": sha256(database_backup)},
        "uploads": {"bytes": uploads_archive.stat().st_size, "sha256": sha256(uploads_archive)},
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for candidate in BACKUP_ROOT.iterdir():
        if candidate == destination or not candidate.is_dir():
            continue
        try:
            created_at = datetime.strptime(candidate.name, "%Y%m%d-%H%M%S")
        except ValueError:
            continue
        if created_at < cutoff:
            shutil.rmtree(candidate)

    print(destination)


if __name__ == "__main__":
    main()
