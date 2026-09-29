"""The Phase 1 -> Phase 2 schema upgrade must keep every document, chunk and vector."""
import json
import sqlite3

import numpy as np

from app.rag.store import LOCAL_USER, Store

PHASE1_SCHEMA = """
CREATE TABLE collections (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE documents (id INTEGER PRIMARY KEY,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    title TEXT NOT NULL, source_type TEXT NOT NULL, source TEXT NOT NULL, sha256 TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0, warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE (collection_id, source));
CREATE TABLE chunks (id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL, header TEXT NOT NULL, text TEXT NOT NULL, meta TEXT NOT NULL, embedding BLOB NOT NULL);
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE VIRTUAL TABLE chunks_fts USING fts5(content, tokenize='porter unicode61');
CREATE TABLE kv (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT INTO kv (key, value) VALUES ('version', 7);
"""


def make_phase1_db(path):
    con = sqlite3.connect(path)
    con.executescript(PHASE1_SCHEMA)
    vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    con.execute("INSERT INTO collections (id, name) VALUES (5, 'computer-vision'), (9, 'mlops')")
    con.execute("INSERT INTO documents (id, collection_id, title, source_type, source, sha256, chunk_count) "
                "VALUES (11, 5, 'CV Notes', 'pdf', 'C:/x/cv.pdf', 'aaa', 1), (12, 9, 'Course', 'youtube', 'https://y', 'bbb', 1)")
    for chunk_id, doc_id, text in ((21, 11, "sobel operator gradient"), (22, 12, "mlflow tracking runs")):
        con.execute("INSERT INTO chunks (id, document_id, ordinal, header, text, meta, embedding) VALUES (?, ?, 0, 'h', ?, ?, ?)",
                    (chunk_id, doc_id, text, json.dumps({"page_start": 1, "page_end": 1}), vec.tobytes()))
        con.execute("INSERT INTO chunks_fts (rowid, content) VALUES (?, ?)", (chunk_id, "h\n" + text))
    con.commit()
    con.close()


def test_phase1_database_is_upgraded_without_losing_data(tmp_path):
    path = tmp_path / "old.db"
    make_phase1_db(path)

    store = Store(path)

    collections = {c["name"]: c for c in store.list_collections()}
    assert set(collections) == {"computer-vision", "mlops"}
    assert collections["computer-vision"]["id"] == 5 and collections["mlops"]["id"] == 9, "ids must be preserved"
    assert all(c["user_id"] == LOCAL_USER for c in collections.values()), "old data belongs to the local owner"
    assert collections["computer-vision"]["documents"] == 1 and collections["computer-vision"]["chunks"] == 1

    (cv_id,) = store.collection_ids(["computer-vision"])
    assert store.bm25_search("sobel", [cv_id], 5)[0][0] == 21
    assert store.dense_search(np.array([1, 0, 0, 0], dtype=np.float32), [cv_id], 5)[0][0] == 21
    assert store.get_chunks([21])[21].meta == {"page_start": 1, "page_end": 1}

    con = sqlite3.connect(path)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert con.execute("PRAGMA user_version").fetchone()[0] == 3
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()


def test_upgraded_database_enforces_per_user_names_and_cascades(tmp_path):
    path = tmp_path / "old.db"
    make_phase1_db(path)
    store = Store(path)

    other = store.get_or_create_collection("computer-vision", user_id=42)
    assert other not in (5, 9), "same name is allowed for another user"
    assert store.collection_ids(["computer-vision"], user_id=42) == [other]
    assert store.collection_ids(["computer-vision"], user_id=LOCAL_USER) == [5]

    assert store.delete_collection(5, user_id=LOCAL_USER) == ["C:/x/cv.pdf"]
    assert store.bm25_search("sobel", None, 5) == [], "FTS rows removed with the collection"
    assert store.get_chunks([21]) == {}, "chunks cascade-deleted"


def test_migration_is_idempotent(tmp_path):
    path = tmp_path / "old.db"
    make_phase1_db(path)
    Store(path)
    again = Store(path)
    assert len(again.list_collections()) == 2
    assert len(again.list_documents()) == 2


def test_fresh_database_gets_the_new_schema(tmp_path):
    store = Store(tmp_path / "fresh.db")
    with store.connect() as con:
        tables = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "sessions", "collections", "documents", "chunks", "jobs", "kv"} <= tables
