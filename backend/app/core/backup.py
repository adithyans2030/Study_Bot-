"""Nightly database backup. Safe to run while the server is writing (WAL mode + SQLite's own
online backup API, which copies a consistent snapshot page by page instead of touching the file).
"""
import logging
import sqlite3
import time
from pathlib import Path

from app.config import Settings

log = logging.getLogger("studybot")
STAMP = "%Y%m%d-%H%M%S"


def backup_now(settings: Settings, keep: int = 14) -> Path | None:
    """Copy the live database into `settings.backups_dir` and delete backups beyond the newest
    `keep`. Returns the new backup's path, or None if there is no database yet to back up."""
    settings.ensure_dirs()
    if not settings.db_path.exists():
        log.info("backup skipped: no database at %s yet", settings.db_path)
        return None

    dest = _unique_name(settings.backups_dir, time.strftime(STAMP))
    source = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    kept = _prune(settings.backups_dir, keep)
    log.info("backed up database to %s (%d backups kept)", dest.name, kept)
    return dest


def _unique_name(backups_dir: Path, stamp: str) -> Path:
    """`studybot.<stamp>.db`, or `.2.db`, `.3.db`, ... if two backups land in the same second
    (real nightly runs never collide; a test loop calling `backup_now` repeatedly can)."""
    candidate = backups_dir / f"studybot.{stamp}.db"
    n = 2
    while candidate.exists():
        candidate = backups_dir / f"studybot.{stamp}.{n}.db"
        n += 1
    return candidate


def _prune(backups_dir: Path, keep: int) -> int:
    """Delete all but the `keep` most recent `studybot.*.db` backups. Returns how many remain."""
    backups = sorted(backups_dir.glob("studybot.*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in backups[keep:]:
        stale.unlink(missing_ok=True)
    return min(len(backups), keep)
