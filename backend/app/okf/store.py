"""OKF Store — SQLite table for OKF nodes with numpy vector search."""
from __future__ import annotations

import json
import logging
import threading
from typing import Sequence

import numpy as np

from app.okf.models import OKFNode, OKFSearchResult

log = logging.getLogger("studybot.okf.store")

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS okf_nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    collection_id   INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    type            TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    body            TEXT    NOT NULL,
    tags            TEXT    NOT NULL DEFAULT '[]',
    trust           TEXT    NOT NULL DEFAULT 'high',
    source_document TEXT    NOT NULL DEFAULT '',
    embedding       BLOB,
    created_at      REAL    NOT NULL DEFAULT (unixepoch('now'))
);
CREATE INDEX IF NOT EXISTS okf_nodes_collection ON okf_nodes (collection_id);
CREATE INDEX IF NOT EXISTS okf_nodes_document   ON okf_nodes (document_id);
CREATE INDEX IF NOT EXISTS okf_nodes_user       ON okf_nodes (user_id);
"""


class OKFStore:
    """Stores OKF nodes in the studybot SQLite database."""

    def __init__(self, store):
        """store is studybot's rag.store.Store instance."""
        self._store = store
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._store.transaction() as con:
            for stmt in CREATE_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    con.execute(stmt)
        log.info("okf_nodes table ensured")

    def insert_nodes(self, nodes: list[OKFNode], embeddings: np.ndarray, document_id: int,
                     collection_id: int, user_id: int) -> list[int]:
        """Insert nodes with their embeddings. Returns list of inserted IDs."""
        if not nodes:
            return []
        inserted = []
        with self._store.transaction() as con:
            for node, vec in zip(nodes, embeddings):
                row_id = con.execute(
                    "INSERT INTO okf_nodes "
                    "(document_id, collection_id, user_id, type, title, description, body, tags, trust, "
                    "source_document, embedding) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (document_id, collection_id, user_id, node.type, node.title, node.description,
                     node.body, json.dumps(node.tags), node.trust, node.source_document,
                     np.ascontiguousarray(vec, dtype=np.float32).tobytes())
                ).lastrowid
                inserted.append(row_id)
        log.info("OKF: stored %d nodes for document %d", len(inserted), document_id)
        return inserted

    def delete_by_document(self, document_id: int) -> int:
        """Delete all nodes for a document. Returns count deleted."""
        with self._store.transaction() as con:
            cur = con.execute("DELETE FROM okf_nodes WHERE document_id = ?", (document_id,))
            return cur.rowcount

    def delete_by_collection(self, collection_id: int, user_id: int) -> int:
        """Delete all nodes in a collection owned by user."""
        with self._store.transaction() as con:
            cur = con.execute(
                "DELETE FROM okf_nodes WHERE collection_id = ? AND user_id = ?",
                (collection_id, user_id)
            )
            return cur.rowcount

    def list_nodes(self, collection_id: int | None = None, user_id: int | None = None,
                   node_type: str | None = None, limit: int = 200) -> list[OKFNode]:
        clauses, params = [], []
        if collection_id is not None:
            clauses.append("collection_id = ?"); params.append(collection_id)
        if user_id is not None:
            clauses.append("user_id = ?"); params.append(user_id)
        if node_type:
            clauses.append("type = ?"); params.append(node_type)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._store.connect() as con:
            rows = con.execute(
                f"SELECT * FROM okf_nodes {where} ORDER BY created_at DESC LIMIT ?", params
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_node(self, node_id: int, user_id: int) -> OKFNode | None:
        with self._store.connect() as con:
            row = con.execute(
                "SELECT * FROM okf_nodes WHERE id = ? AND user_id = ?", (node_id, user_id)
            ).fetchone()
        return self._row_to_node(row) if row else None

    def search(self, query_vector: np.ndarray, collection_id: int | None,
               user_id: int | None, k: int = 10) -> list[OKFSearchResult]:
        """Cosine similarity search over OKF node embeddings."""
        clauses, params = ["embedding IS NOT NULL"], []
        if collection_id is not None:
            clauses.append("collection_id = ?"); params.append(collection_id)
        if user_id is not None:
            clauses.append("user_id = ?"); params.append(user_id)
        where = "WHERE " + " AND ".join(clauses)
        with self._store.connect() as con:
            rows = con.execute(
                f"SELECT id, embedding, type, title, description, body, tags, trust, "
                f"source_document, document_id, collection_id, user_id FROM okf_nodes {where}",
                params
            ).fetchall()
        if not rows:
            return []

        ids = [r["id"] for r in rows]
        matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
        q = np.asarray(query_vector, dtype=np.float32)
        scores = matrix @ q
        top_k = min(k, len(ids))
        top_idx = np.argsort(-scores)[:top_k]

        results = []
        for i in top_idx:
            node = self._row_to_node(rows[i])
            results.append(OKFSearchResult(node=node, score=float(scores[i])))
        return results

    def stats(self, collection_id: int | None, user_id: int | None) -> dict:
        clauses, params = [], []
        if collection_id is not None:
            clauses.append("collection_id = ?"); params.append(collection_id)
        if user_id is not None:
            clauses.append("user_id = ?"); params.append(user_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._store.connect() as con:
            total = con.execute(f"SELECT COUNT(*) FROM okf_nodes {where}", params).fetchone()[0]
            by_type = con.execute(
                f"SELECT type, COUNT(*) as n FROM okf_nodes {where} GROUP BY type", params
            ).fetchall()
            docs = con.execute(
                f"SELECT COUNT(DISTINCT document_id) FROM okf_nodes {where}", params
            ).fetchone()[0]
        return {
            "total_nodes": total,
            "documents_covered": docs,
            "nodes_by_type": {r["type"]: r["n"] for r in by_type},
        }

    @staticmethod
    def _row_to_node(row) -> OKFNode:
        return OKFNode(
            node_id=row["id"],
            document_id=row["document_id"],
            collection_id=row["collection_id"],
            user_id=row["user_id"],
            type=row["type"],
            title=row["title"],
            description=row["description"],
            body=row["body"],
            tags=json.loads(row["tags"]),
            trust=row["trust"],
            source_document=row["source_document"],
        )
