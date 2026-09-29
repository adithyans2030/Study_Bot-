"""SQLite-backed ingest job queue. Jobs survive restarts: a job interrupted mid-run is put back."""
import json
import time
import uuid
from dataclasses import dataclass

from app.rag.store import Store

PENDING, RUNNING, DONE, FAILED = "pending", "running", "done", "failed"
TERMINAL = (DONE, FAILED)
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Job:
    id: str
    user_id: int
    kind: str  # file | youtube | reindex
    source: str
    collection: str
    title: str | None
    force: bool
    status: str
    stage: str
    error: str | None
    document_id: int | None
    chunks: int | None
    warnings: list[str]
    attempts: int
    created_at: float
    updated_at: float

    def public(self) -> dict:
        """What the API shows: never the server-side file path."""
        return {"id": self.id, "kind": self.kind, "collection": self.collection, "title": self.title,
                "status": self.status, "stage": self.stage, "error": self.error,
                "document_id": self.document_id, "chunks": self.chunks, "warnings": self.warnings,
                "created_at": self.created_at, "updated_at": self.updated_at}


def _job(row) -> Job:
    return Job(row["id"], row["user_id"], row["kind"], row["source"], row["collection"], row["title"],
               bool(row["force"]), row["status"], row["stage"], row["error"], row["document_id"], row["chunks"],
               json.loads(row["warnings"]), row["attempts"], row["created_at"], row["updated_at"])


class JobQueue:
    def __init__(self, store: Store):
        self.store = store

    def create(self, user_id: int, kind: str, source: str, collection: str, title: str | None = None,
               force: bool = False) -> Job:
        job_id, now = uuid.uuid4().hex, time.time()
        with self.store.transaction() as con:
            con.execute("INSERT INTO jobs (id, user_id, kind, source, collection, title, force, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (job_id, user_id, kind, source, collection, title, int(force), now, now))
        return self.get(job_id)

    def get(self, job_id: str, user_id: int | None = None) -> Job | None:
        with self.store.connect() as con:
            sql, params = "SELECT * FROM jobs WHERE id = ?", [job_id]
            if user_id is not None:
                sql += " AND user_id = ?"
                params.append(user_id)
            row = con.execute(sql, params).fetchone()
        return _job(row) if row else None

    def list_for_user(self, user_id: int, limit: int = 30) -> list[Job]:
        with self.store.connect() as con:
            rows = con.execute("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                               (user_id, limit)).fetchall()
        return [_job(r) for r in rows]

    def claim_next(self) -> Job | None:
        """Atomically take the oldest pending job and mark it running."""
        with self.store.transaction() as con:
            row = con.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1", (PENDING,)).fetchone()
            if row is None:
                return None
            con.execute("UPDATE jobs SET status = ?, stage = 'starting', attempts = attempts + 1, updated_at = ? "
                        "WHERE id = ?", (RUNNING, time.time(), row["id"]))
            claimed = con.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()
        return _job(claimed)

    def set_stage(self, job_id: str, stage: str) -> None:
        with self.store.transaction() as con:
            con.execute("UPDATE jobs SET stage = ?, updated_at = ? WHERE id = ? AND status = ?",
                        (stage, time.time(), job_id, RUNNING))

    def finish(self, job_id: str, *, error: str | None = None, document_id: int | None = None,
               chunks: int | None = None, warnings: list[str] | None = None, stage: str = "") -> None:
        status = FAILED if error else DONE
        with self.store.transaction() as con:
            con.execute("UPDATE jobs SET status = ?, stage = ?, error = ?, document_id = ?, chunks = ?, "
                        "warnings = ?, updated_at = ? WHERE id = ?",
                        (status, stage or ("failed" if error else "done"), error, document_id, chunks,
                         json.dumps(warnings or []), time.time(), job_id))

    def recover_interrupted(self) -> int:
        """At startup: jobs left 'running' by a crash or restart go back to pending (up to
        MAX_ATTEMPTS tries), then fail. Indexing a document is atomic, so a retry is safe."""
        with self.store.transaction() as con:
            con.execute("UPDATE jobs SET status = ?, error = 'Interrupted too many times; please upload again.', "
                        "stage = 'failed', updated_at = ? WHERE status = ? AND attempts >= ?",
                        (FAILED, time.time(), RUNNING, MAX_ATTEMPTS))
            return con.execute("UPDATE jobs SET status = ?, stage = 'queued again', updated_at = ? WHERE status = ?",
                               (PENDING, time.time(), RUNNING)).rowcount
