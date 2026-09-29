"""Single-file SQLite store: accounts, documents, chunks, FTS5 (BM25) index, vectors and job queue.

Why one file instead of SQLite + a vector database: replacing a document (delete old chunks,
insert new chunks, vectors and text index) is ONE transaction, so a crash can never leave
the two stores out of sync, and a backup is one file copy. Dense search is an exact numpy
dot product over the collection's vectors, which is instant at study-material scale
(tens of thousands of chunks). Swap in an ANN index only if the corpus outgrows that.

Ownership: every collection belongs to a user (`user_id`). User 0 is the "local" owner used by
the command line before any account exists; the first account created adopts those collections.
Search functions take explicit collection ids, so isolation is enforced where names are resolved
to ids (`collection_ids`), never by the caller remembering to filter.
"""
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from app.ingest.types import Chunk, LoadedDocument

LOCAL_USER = 0
SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 0,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, name)
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (collection_id, source)
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    header TEXT NOT NULL,
    text TEXT NOT NULL,
    meta TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(content, tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    collection TEXT NOT NULL,
    title TEXT,
    force INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    stage TEXT NOT NULL DEFAULT '',
    error TEXT,
    document_id INTEGER,
    chunks INTEGER,
    warnings TEXT NOT NULL DEFAULT '[]',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    meta TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT OR IGNORE INTO kv (key, value) VALUES ('version', 0);
"""

_STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from how i if in into is it its me my of on or "
    "our so than that the their them then there these they this to us was we what when where "
    "which who why will with you your about between explain describe difference".split()
)


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    document_id: int
    doc_title: str
    source_type: str
    source: str
    ordinal: int
    header: str
    text: str
    meta: dict


@dataclass(frozen=True)
class DocumentRecord:
    id: int
    collection: str
    title: str
    source_type: str
    source: str
    sha256: str
    chunk_count: int
    warnings: list[str]
    collection_id: int = 0
    created_at: str = ""


def fts_query(text: str) -> str | None:
    """Turn free text into a safe FTS5 OR-query of quoted content words (None if nothing left)."""
    words = [w for w in re.findall(r"[A-Za-z0-9]+", text.lower()) if w not in _STOPWORDS and len(w) > 1]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words)) or None


def _migrate_collections_to_v2(con: sqlite3.Connection) -> None:
    """Phase 1 databases have collections(name UNIQUE) with no owner. Rebuild the table with a
    user_id (0 = local) and UNIQUE(user_id, name), keeping ids so documents stay linked."""
    columns = [row["name"] for row in con.execute("PRAGMA table_info(collections)")]
    if not columns or "user_id" in columns:
        return
    con.execute("PRAGMA foreign_keys=OFF")  # must be set outside a transaction
    con.execute("BEGIN IMMEDIATE")
    try:
        con.execute("CREATE TABLE collections_v2 (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL DEFAULT 0, "
                    "name TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE (user_id, name))")
        con.execute("INSERT INTO collections_v2 (id, user_id, name, created_at) "
                    "SELECT id, 0, name, created_at FROM collections")
        con.execute("DROP TABLE collections")
        con.execute("ALTER TABLE collections_v2 RENAME TO collections")
        problems = con.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise sqlite3.IntegrityError(f"foreign key check failed after migration: {len(problems)} problem(s)")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[tuple, tuple[int, np.ndarray, np.ndarray]] = {}
        with self.connect() as con:
            _migrate_collections_to_v2(con)
            con.executescript(SCHEMA)
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def transaction(self):
        """A write transaction. Bumps the data version so cached vector matrices are rebuilt."""
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
            except BaseException:
                con.execute("ROLLBACK")
                raise
            con.execute("UPDATE kv SET value = value + 1 WHERE key = 'version'")
            con.execute("COMMIT")

    # ---- collections -------------------------------------------------------------------

    def get_or_create_collection(self, name: str, user_id: int = LOCAL_USER) -> int:
        with self.transaction() as con:
            con.execute("INSERT OR IGNORE INTO collections (user_id, name) VALUES (?, ?)", (user_id, name))
            return con.execute("SELECT id FROM collections WHERE user_id = ? AND name = ?",
                               (user_id, name)).fetchone()["id"]

    def collection_ids(self, names: Iterable[str] | None, user_id: int = LOCAL_USER) -> list[int]:
        """Resolve a user's collection names to ids (None = all of that user's collections).
        Unknown names raise KeyError. This is the isolation boundary: ids of other users'
        collections can never come out of here."""
        with self.connect() as con:
            if names is None:
                return [r["id"] for r in con.execute(
                    "SELECT id FROM collections WHERE user_id = ? ORDER BY name", (user_id,))]
            ids = []
            for name in names:
                row = con.execute("SELECT id FROM collections WHERE user_id = ? AND name = ?",
                                  (user_id, name)).fetchone()
                if row is None:
                    raise KeyError(name)
                ids.append(row["id"])
            return ids

    def list_collections(self, user_id: int | None = None) -> list[dict]:
        with self.connect() as con:
            where, params = ("WHERE c.user_id = ?", (user_id,)) if user_id is not None else ("", ())
            rows = con.execute(
                "SELECT c.id, c.user_id, c.name, COUNT(DISTINCT d.id) AS documents, COUNT(ch.id) AS chunks "
                "FROM collections c LEFT JOIN documents d ON d.collection_id = c.id "
                f"LEFT JOIN chunks ch ON ch.document_id = d.id {where} GROUP BY c.id ORDER BY c.name",
                params).fetchall()
            return [dict(r) for r in rows]

    def delete_collection(self, collection_id: int, user_id: int) -> list[str] | None:
        """Delete a collection and everything in it. Returns the deleted documents' `source`
        values (so the caller can remove uploaded files), or None if it is not this user's."""
        with self.transaction() as con:
            owned = con.execute("SELECT 1 FROM collections WHERE id = ? AND user_id = ?",
                                (collection_id, user_id)).fetchone()
            if not owned:
                return None
            docs = con.execute("SELECT id, source FROM documents WHERE collection_id = ?", (collection_id,)).fetchall()
            for doc in docs:
                self._delete_document(con, doc["id"])
            con.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
            return [d["source"] for d in docs]

    def adopt_legacy_collections(self, user_id: int) -> int:
        """Give collections created before any account existed (user 0) to `user_id`."""
        with self.transaction() as con:
            return con.execute("UPDATE OR IGNORE collections SET user_id = ? WHERE user_id = ?",
                               (user_id, LOCAL_USER)).rowcount

    # ---- documents ---------------------------------------------------------------------

    _DOC_SELECT = ("SELECT d.*, c.name AS collection FROM documents d "
                   "JOIN collections c ON c.id = d.collection_id")

    def find_document(self, collection_id: int, source: str) -> DocumentRecord | None:
        with self.connect() as con:
            row = con.execute(f"{self._DOC_SELECT} WHERE d.collection_id = ? AND d.source = ?",
                              (collection_id, source)).fetchone()
            return self._document(row) if row else None

    def find_document_by_hash(self, collection_id: int, sha256: str) -> DocumentRecord | None:
        with self.connect() as con:
            row = con.execute(f"{self._DOC_SELECT} WHERE d.collection_id = ? AND d.sha256 = ? ORDER BY d.id LIMIT 1",
                              (collection_id, sha256)).fetchone()
            return self._document(row) if row else None

    def get_document(self, document_id: int, user_id: int | None = None) -> DocumentRecord | None:
        with self.connect() as con:
            sql, params = f"{self._DOC_SELECT} WHERE d.id = ?", [document_id]
            if user_id is not None:
                sql += " AND c.user_id = ?"
                params.append(user_id)
            row = con.execute(sql, params).fetchone()
            return self._document(row) if row else None

    def list_documents(self, collection_id: int | None = None, user_id: int | None = None) -> list[DocumentRecord]:
        with self.connect() as con:
            clauses, params = [], []
            if collection_id is not None:
                clauses.append("d.collection_id = ?")
                params.append(collection_id)
            if user_id is not None:
                clauses.append("c.user_id = ?")
                params.append(user_id)
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            return [self._document(r) for r in con.execute(f"{self._DOC_SELECT}{where} ORDER BY c.name, d.title", params)]

    @staticmethod
    def _document(row) -> DocumentRecord:
        return DocumentRecord(row["id"], row["collection"], row["title"], row["source_type"], row["source"],
                              row["sha256"], row["chunk_count"], json.loads(row["warnings"]),
                              row["collection_id"], row["created_at"])

    @staticmethod
    def _delete_document(con, document_id: int) -> None:
        con.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE document_id = ?)",
                    (document_id,))
        con.execute("DELETE FROM documents WHERE id = ?", (document_id,))  # chunks cascade

    def delete_document(self, document_id: int, user_id: int | None = None) -> bool:
        """Delete a document. If user_id is given, only if it belongs to that user."""
        with self.transaction() as con:
            sql, params = ("SELECT 1 FROM documents d JOIN collections c ON c.id = d.collection_id WHERE d.id = ?",
                           [document_id])
            if user_id is not None:
                sql += " AND c.user_id = ?"
                params.append(user_id)
            exists = con.execute(sql, params).fetchone()
            if exists:
                self._delete_document(con, document_id)
            return bool(exists)

    def add_document(self, collection_id: int, doc: LoadedDocument, chunks: Sequence[Chunk],
                     vectors: np.ndarray) -> int:
        """Insert a document, replacing any earlier copy from the same source, atomically."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        with self.transaction() as con:
            old = con.execute("SELECT id FROM documents WHERE collection_id = ? AND source = ?",
                              (collection_id, doc.source)).fetchone()
            if old:
                self._delete_document(con, old["id"])
            document_id = con.execute(
                "INSERT INTO documents (collection_id, title, source_type, source, sha256, chunk_count, warnings) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (collection_id, doc.title, doc.source_type, doc.source, doc.content_hash, len(chunks),
                 json.dumps(doc.warnings))).lastrowid
            for chunk, vector in zip(chunks, vectors):
                chunk_id = con.execute(
                    "INSERT INTO chunks (document_id, ordinal, header, text, meta, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                    (document_id, chunk.ordinal, chunk.header, chunk.text, json.dumps(chunk.meta),
                     vector.tobytes())).lastrowid
                con.execute("INSERT INTO chunks_fts (rowid, content) VALUES (?, ?)",
                            (chunk_id, chunk.header + "\n" + chunk.text))
            return document_id

    # ---- search ------------------------------------------------------------------------

    @staticmethod
    def _scope(collection_ids: Sequence[int] | None) -> tuple[str, list]:
        if collection_ids is None:
            return "", []
        marks = ",".join("?" for _ in collection_ids) or "NULL"
        return f" AND d.collection_id IN ({marks})", list(collection_ids)

    def _version(self, con) -> int:
        return con.execute("SELECT value FROM kv WHERE key = 'version'").fetchone()["value"]

    def _matrix(self, collection_ids: Sequence[int] | None) -> tuple[np.ndarray, np.ndarray]:
        key = None if collection_ids is None else tuple(sorted(collection_ids))
        with self.connect() as con:
            version = self._version(con)
            with self._lock:
                cached = self._cache.get(key)
            if cached and cached[0] == version:
                return cached[1], cached[2]
            scope_sql, params = self._scope(collection_ids)
            rows = con.execute(
                "SELECT c.id, c.embedding FROM chunks c JOIN documents d ON d.id = c.document_id "
                f"WHERE 1 = 1{scope_sql} ORDER BY c.id", params).fetchall()
        ids = np.array([r["id"] for r in rows], dtype=np.int64)
        matrix = (np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
                  if rows else np.zeros((0, 0), dtype=np.float32))
        with self._lock:
            self._cache[key] = (version, ids, matrix)
        return ids, matrix

    def dense_search(self, query_vector: np.ndarray, collection_ids: Sequence[int] | None,
                     k: int) -> list[tuple[int, float]]:
        """Exact cosine search (vectors are unit length). Returns [(chunk_id, similarity)], best first."""
        ids, matrix = self._matrix(collection_ids)
        if len(ids) == 0:
            return []
        scores = matrix @ np.asarray(query_vector, dtype=np.float32)
        k = min(k, len(ids))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(ids[i]), float(scores[i])) for i in top]

    def bm25_search(self, query: str, collection_ids: Sequence[int] | None, k: int) -> list[tuple[int, float]]:
        match = fts_query(query)
        if match is None:
            return []
        scope_sql, params = self._scope(collection_ids)
        with self.connect() as con:
            rows = con.execute(
                "SELECT chunks_fts.rowid AS id, bm25(chunks_fts) AS score FROM chunks_fts "
                "JOIN chunks c ON c.id = chunks_fts.rowid JOIN documents d ON d.id = c.document_id "
                f"WHERE chunks_fts MATCH ?{scope_sql} ORDER BY score LIMIT ?", [match, *params, k]).fetchall()
        return [(r["id"], -r["score"]) for r in rows]  # FTS5 bm25 is lower-is-better

    def cosine(self, chunk_ids: Sequence[int], query_vector: np.ndarray) -> dict[int, float]:
        if not chunk_ids:
            return {}
        marks = ",".join("?" for _ in chunk_ids)
        with self.connect() as con:
            rows = con.execute(f"SELECT id, embedding FROM chunks WHERE id IN ({marks})", list(chunk_ids)).fetchall()
        q = np.asarray(query_vector, dtype=np.float32)
        return {r["id"]: float(np.frombuffer(r["embedding"], dtype=np.float32) @ q) for r in rows}

    def get_chunks(self, chunk_ids: Sequence[int]) -> dict[int, ChunkRecord]:
        if not chunk_ids:
            return {}
        marks = ",".join("?" for _ in chunk_ids)
        with self.connect() as con:
            rows = con.execute(
                "SELECT c.id, c.document_id, c.ordinal, c.header, c.text, c.meta, d.title, d.source_type, d.source "
                f"FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id IN ({marks})",
                list(chunk_ids)).fetchall()
        return {r["id"]: ChunkRecord(r["id"], r["document_id"], r["title"], r["source_type"], r["source"],
                                     r["ordinal"], r["header"], r["text"], json.loads(r["meta"])) for r in rows}
