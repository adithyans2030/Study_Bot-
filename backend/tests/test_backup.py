import sqlite3
import time

from app.core.backup import backup_now


def make_db(path, value="hello"):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT, v TEXT)")
    con.execute("DELETE FROM kv")
    con.execute("INSERT INTO kv VALUES ('x', ?)", (value,))
    con.commit()
    con.close()


def test_no_database_yet_is_not_an_error(settings):
    assert backup_now(settings) is None


def test_backup_copies_a_consistent_snapshot(settings):
    make_db(settings.db_path, "first")
    dest = backup_now(settings)
    assert dest is not None and dest.exists() and dest.parent == settings.backups_dir

    con = sqlite3.connect(dest)
    assert con.execute("SELECT v FROM kv").fetchone()[0] == "first"
    con.close()


def test_old_backups_beyond_the_limit_are_deleted(settings):
    make_db(settings.db_path)
    paths = []
    for _ in range(5):
        paths.append(backup_now(settings, keep=3))
        time.sleep(0.01)  # each backup needs a distinct timestamp in its filename

    remaining = sorted(settings.backups_dir.glob("studybot.*.db"))
    assert len(remaining) == 3
    assert set(p.name for p in remaining) == {p.name for p in paths[-3:]}


def test_unrelated_files_in_the_backups_folder_are_left_alone(settings):
    make_db(settings.db_path)
    settings.ensure_dirs()
    keepsake = settings.backups_dir / "notes.txt"
    keepsake.write_text("not a backup")

    backup_now(settings, keep=1)
    assert keepsake.exists()
