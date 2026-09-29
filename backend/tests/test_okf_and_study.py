"""Tests for OKF knowledge graph and Phase 5 study endpoints."""
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.okf.models import OKFNode
from app.okf.store import OKFStore
from app.rag.store import Store


def test_okf_models():
    node = OKFNode(
        type="concept",
        title="Dynamic Programming",
        description="Breaking problems into overlapping subproblems.",
        body="Dynamic Programming (DP) is an algorithmic paradigm that solves complex problems by breaking them down into simpler subproblems.",
        tags=["algorithms", "optimization"],
    )
    assert node.type == "concept"
    assert node.title == "Dynamic Programming"
    assert node.tags == ["algorithms", "optimization"]
    assert node.trust == "high"


def test_okf_store(tmp_path: Path):
    db_file = tmp_path / "studybot.db"
    base_store = Store(db_file)
    okf_store = OKFStore(base_store)

    user_id = 1
    col_id = base_store.get_or_create_collection("Computer Science", user_id=user_id)

    # Insert a dummy document to satisfy foreign key
    with base_store.transaction() as con:
        doc_id = con.execute(
            "INSERT INTO documents (collection_id, title, source_type, source, sha256, chunk_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (col_id, "Lecture 1", "pdf", "notes.pdf", "dummyhash", 0)
        ).lastrowid

    nodes = [
        OKFNode(
            type="concept",
            title="Gradient Descent",
            description="First-order iterative optimization algorithm.",
            body="Gradient descent is used for finding local minimum of a differentiable function.",
            tags=["ml", "optimization"],
            source_document="Lecture 1",
        ),
        OKFNode(
            type="formula",
            title="Ohm's Law",
            description="Relationship between voltage, current, and resistance.",
            body="V = I * R",
            tags=["physics", "circuits"],
            source_document="Lecture 1",
        ),
    ]

    embeddings = np.random.randn(2, 384).astype(np.float32)
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)

    inserted = okf_store.insert_nodes(
        nodes=nodes,
        embeddings=embeddings,
        document_id=doc_id,
        collection_id=col_id,
        user_id=user_id,
    )
    assert len(inserted) == 2

    # Listing
    listed = okf_store.list_nodes(collection_id=col_id, user_id=user_id)
    assert len(listed) == 2

    # Stats
    stats = okf_store.stats(collection_id=col_id, user_id=user_id)
    assert stats["total_nodes"] == 2
    assert stats["nodes_by_type"]["concept"] == 1
    assert stats["nodes_by_type"]["formula"] == 1

    # Search
    query = embeddings[0]
    results = okf_store.search(query, collection_id=col_id, user_id=user_id, k=5)
    assert len(results) >= 1
    assert results[0].node.title == "Gradient Descent"


def test_routes_registered():
    app = create_app()
    client = TestClient(app)

    # Health check
    res = client.get("/api/health")
    assert res.status_code == 200

    # Knowledge endpoints are protected by auth
    res_k = client.get("/api/knowledge")
    assert res_k.status_code in (401, 403)

    # Study endpoints are protected by auth
    res_s = client.post("/api/collections/1/study/summarize", json={"length": "short"})
    assert res_s.status_code in (401, 403)