"""Unit tests for accounts, the login limiter, the job queue and upload safety."""
import sqlite3
import zipfile

import pytest

from app.core import uploads
from app.core.accounts import AccountError, Accounts, LoginLimiter
from app.core.jobs import MAX_ATTEMPTS, JobQueue
from app.rag.store import LOCAL_USER, Store
from tests.fixtures import notes_docx, notes_pdf


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


# ---- accounts ----------------------------------------------------------------------------

def test_first_user_is_admin_and_adopts_local_collections(store):
    store.get_or_create_collection("old-notes", LOCAL_USER)
    accounts = Accounts(store)
    first = accounts.create_user("Alice", "correct horse")
    second = accounts.create_user("bob", "another passphrase")
    assert first.is_admin and not second.is_admin
    assert accounts.owner_id() == first.id
    assert [c["name"] for c in store.list_collections(first.id)] == ["old-notes"]
    assert store.list_collections(second.id) == []
    assert store.list_collections(LOCAL_USER) == []


@pytest.mark.parametrize("username,password,message", [
    ("ab", "long enough pw", "Username"), ("bad name!", "long enough pw", "Username"),
    ("alice", "short", "at least 8"), ("alice", "x" * 200, "at most"),
])
def test_invalid_credentials_are_rejected(store, username, password, message):
    with pytest.raises(AccountError, match=message):
        Accounts(store).create_user(username, password)


def test_duplicate_usernames_are_rejected_case_insensitively(store):
    accounts = Accounts(store)
    accounts.create_user("alice", "correct horse")
    with pytest.raises(AccountError, match="already taken"):
        accounts.create_user("ALICE", "different pass")


def test_authentication(store):
    accounts = Accounts(store)
    accounts.create_user("alice", "correct horse")
    assert accounts.authenticate("alice", "correct horse").username == "alice"
    assert accounts.authenticate("ALICE ", "correct horse") is not None, "username is normalised"
    assert accounts.authenticate("alice", "wrong") is None
    assert accounts.authenticate("nobody", "correct horse") is None
    assert accounts.authenticate("alice", "") is None


def test_passwords_and_session_tokens_are_not_stored_in_clear(store, tmp_path):
    accounts = Accounts(store)
    user = accounts.create_user("alice", "correct horse")
    token = accounts.create_session(user.id)
    con = sqlite3.connect(tmp_path / "t.db")
    dump = " ".join(str(v) for row in con.execute("SELECT * FROM users") for v in row)
    dump += " ".join(str(v) for row in con.execute("SELECT * FROM sessions") for v in row)
    assert "correct horse" not in dump and token not in dump
    assert "$argon2id$" in dump


def test_sessions_work_expire_and_can_be_ended(store):
    accounts = Accounts(store)
    user = accounts.create_user("alice", "correct horse")
    token = accounts.create_session(user.id)
    assert accounts.user_for_token(token).id == user.id
    assert accounts.user_for_token("forged") is None and accounts.user_for_token(None) is None
    accounts.end_session(token)
    assert accounts.user_for_token(token) is None

    accounts.session_seconds = -1
    expired = accounts.create_session(user.id)
    assert accounts.user_for_token(expired) is None


def test_login_limiter_blocks_then_recovers():
    now = [0.0]
    limiter = LoginLimiter(limit=3, window=60, clock=lambda: now[0])
    for _ in range(3):
        assert limiter.retry_after("k") == 0
        limiter.record_failure("k")
    assert limiter.retry_after("k") > 0
    assert limiter.retry_after("other") == 0
    now[0] = 61
    assert limiter.retry_after("k") == 0
    limiter.record_failure("k")
    limiter.reset("k")
    assert limiter.retry_after("k") == 0


# ---- job queue ---------------------------------------------------------------------------

def test_jobs_are_claimed_once_in_order(store):
    jobs = JobQueue(store)
    a = jobs.create(1, "file", "/x/a.pdf", "cv", "A")
    b = jobs.create(1, "youtube", "https://y", "cv")
    first, second = jobs.claim_next(), jobs.claim_next()
    assert (first.id, second.id) == (a.id, b.id)
    assert first.status == "running" and first.attempts == 1
    assert jobs.claim_next() is None


def test_job_lifecycle_and_public_view_hides_paths(store):
    jobs = JobQueue(store)
    job = jobs.create(1, "file", "C:/secret/uploads/abc.pdf", "cv", "Notes")
    jobs.claim_next()
    jobs.set_stage(job.id, "embedding")
    assert jobs.get(job.id).stage == "embedding"
    jobs.finish(job.id, document_id=7, chunks=12, warnings=["w"])
    done = jobs.get(job.id)
    assert (done.status, done.document_id, done.chunks, done.warnings) == ("done", 7, 12, ["w"])
    assert "secret" not in str(done.public()) and "source" not in done.public()
    failed = jobs.create(1, "file", "/x", "cv")
    jobs.finish(failed.id, error="bad file")
    assert jobs.get(failed.id).status == "failed" and jobs.get(failed.id).error == "bad file"


def test_jobs_are_private_to_their_user(store):
    jobs = JobQueue(store)
    job = jobs.create(1, "file", "/x", "cv")
    assert jobs.get(job.id, user_id=1) is not None
    assert jobs.get(job.id, user_id=2) is None
    assert jobs.list_for_user(2) == []


def test_interrupted_jobs_are_requeued_then_eventually_failed(store):
    jobs = JobQueue(store)
    job = jobs.create(1, "file", "/x", "cv")
    jobs.claim_next()  # attempt 1, "crash" before finishing
    assert jobs.recover_interrupted() == 1
    assert jobs.get(job.id).status == "pending"
    for _ in range(MAX_ATTEMPTS - 1):
        jobs.claim_next()
        jobs.recover_interrupted()
    assert jobs.get(job.id).status == "failed"
    assert "Interrupted" in jobs.get(job.id).error


# ---- uploads -----------------------------------------------------------------------------

class FakeUpload:
    def __init__(self, data: bytes):
        self._data, self._pos = data, 0

    async def read(self, size=-1):
        chunk = self._data[self._pos:] if size < 0 else self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


def run(coro):
    import asyncio
    return asyncio.run(coro)


def test_display_title_is_sanitised():
    assert uploads.display_title("C:\\Users\\me\\Unit_1 Notes.pdf") == "Unit 1 Notes"
    assert uploads.display_title("../../etc/passwd") == "passwd"
    assert uploads.display_title("a\x00b\x1fc.pdf") == "abc"
    assert uploads.display_title("") == "Untitled" and uploads.display_title(None) == "Untitled"
    assert len(uploads.display_title("x" * 500 + ".pdf")) == 120


def test_sniff_kind_uses_contents_not_names(tmp_path):
    pdf, docx = notes_pdf(tmp_path / "a.pdf"), notes_docx(tmp_path / "b.docx")
    assert uploads.sniff_kind(pdf) == "pdf" and uploads.sniff_kind(docx) == "docx"
    text = tmp_path / "fake.pdf"
    text.write_text("just text, not a pdf")
    with pytest.raises(uploads.UploadError) as unsupported:
        uploads.sniff_kind(text)
    assert unsupported.value.status == 415
    ole = tmp_path / "old.doc"
    ole.write_bytes(b"\xd0\xcf\x11\xe0" + b"\0" * 100)
    with pytest.raises(uploads.UploadError, match="Old .doc"):
        uploads.sniff_kind(ole)
    plain_zip = tmp_path / "x.zip"
    with zipfile.ZipFile(plain_zip, "w") as z:
        z.writestr("readme.txt", "hi")
    with pytest.raises(uploads.UploadError, match="ZIP file"):
        uploads.sniff_kind(plain_zip)
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"PK\x03\x04 not really a zip")
    with pytest.raises(uploads.UploadError, match="damaged"):
        uploads.sniff_kind(broken)


def test_zip_bombs_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UNCOMPRESSED_BYTES", 1000)
    bomb = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "0" * 50_000)
    with pytest.raises(uploads.UploadError, match="unreasonable size"):
        uploads.sniff_kind(bomb)


def test_save_upload_stores_under_random_name_with_detected_extension(tmp_path):
    data = notes_pdf(tmp_path / "src.pdf").read_bytes()
    path, kind = run(uploads.save_upload(FakeUpload(data), tmp_path / "up" / "1", 10_000_000))
    assert kind == "pdf" and path.suffix == ".pdf" and path.parent == tmp_path / "up" / "1"
    assert path.read_bytes() == data and "src" not in path.name
    assert [p.name for p in path.parent.iterdir()] == [path.name], "no partial file left behind"


@pytest.mark.parametrize("data,status", [(b"", 400), (b"plain text" * 10, 415), (b"%PDF-" + b"0" * 3000, 413)])
def test_save_upload_failures_leave_nothing_behind(tmp_path, data, status):
    directory = tmp_path / "up"
    with pytest.raises(uploads.UploadError) as err:
        run(uploads.save_upload(FakeUpload(data), directory, 2000))
    assert err.value.status == status
    assert list(directory.iterdir()) == []


def test_remove_upload_only_touches_files_inside_the_uploads_dir(tmp_path):
    inside_dir = tmp_path / "uploads"
    inside_dir.mkdir()
    inside, outside = inside_dir / "a.pdf", tmp_path / "keep.pdf"
    inside.write_bytes(b"x")
    outside.write_bytes(b"x")
    assert uploads.remove_upload(str(outside), inside_dir) is False and outside.exists()
    assert uploads.remove_upload(str(inside_dir / ".." / "keep.pdf"), inside_dir) is False and outside.exists()
    assert uploads.remove_upload(str(inside), inside_dir) is True and not inside.exists()
    assert uploads.remove_upload("https://www.youtube.com/watch?v=x", inside_dir) is False
