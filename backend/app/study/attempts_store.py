"""Quiz attempt history, for ranking topics by tested performance (see planner.py).

An append-only log, not an upsert-per-node row: each submission is a plain INSERT (no
read-modify-write races), and accuracy becomes a running average across retries instead of
"last attempt only" - a topic gotten wrong once and right five times since should read as
known, not weak.

No foreign key on node_id: OKF nodes can legitimately disappear (re-ingest, document delete -
okf_nodes.document_id already cascades) between when a quiz was generated, answered, and a plan
was built from it. Not having the FK means a submission can never fail on a stale id, and the
planner looks up stats from a plain dict keyed by currently-live node ids rather than a SQL JOIN,
so an orphaned row is simply never retrieved - inert by construction, not by cascade behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS node_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    collection_id INTEGER NOT NULL,
    node_id       INTEGER,
    correct       INTEGER NOT NULL,
    created_at    REAL NOT NULL DEFAULT (unixepoch('now'))
);
CREATE INDEX IF NOT EXISTS node_attempts_node     ON node_attempts (node_id);
CREATE INDEX IF NOT EXISTS node_attempts_user_col ON node_attempts (user_id, collection_id);
"""


@dataclass(frozen=True)
class NodeAttemptStats:
    attempts: int
    correct: int
    accuracy: float
    last_attempt_at: float


class AttemptsStore:
    """Stores quiz attempt history in the studybot SQLite database."""

    def __init__(self, store):
        """store is studybot's rag.store.Store instance."""
        self._store = store
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._store.transaction() as con:
            for stmt in CREATE_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    con.execute(stmt)

    def record_attempts(self, user_id: int, collection_id: int,
                        rows: list[tuple[int | None, bool]]) -> int:
        """Record every answer from one submitted quiz/flashcard session in a single transaction."""
        if not rows:
            return 0
        with self._store.transaction() as con:
            con.executemany(
                "INSERT INTO node_attempts (user_id, collection_id, node_id, correct) VALUES (?, ?, ?, ?)",
                [(user_id, collection_id, node_id, int(correct)) for node_id, correct in rows],
            )
        return len(rows)

    def node_stats(self, collection_id: int, user_id: int) -> dict[int, NodeAttemptStats]:
        """Per-node attempt/accuracy/recency aggregates, for nodes that have at least one
        attribution-able (node_id is not null) attempt."""
        with self._store.connect() as con:
            rows = con.execute(
                "SELECT node_id, COUNT(*) AS n, SUM(correct) AS c, MAX(created_at) AS last "
                "FROM node_attempts WHERE collection_id = ? AND user_id = ? AND node_id IS NOT NULL "
                "GROUP BY node_id",
                (collection_id, user_id),
            ).fetchall()
        return {
            row["node_id"]: NodeAttemptStats(
                attempts=row["n"], correct=row["c"], accuracy=row["c"] / row["n"],
                last_attempt_at=row["last"],
            )
            for row in rows
        }
