"""Tests for OKF knowledge graph and Phase 5 study endpoints."""
import json
import types
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

import app.api.study as study_module
from app.core.ollama import ChatChunk
from app.main import create_app
from app.okf.models import OKFNode
from app.okf.store import OKFStore
from app.rag.pipeline import StudyBot
from app.rag.store import Store

PASSWORD = "correct horse battery"


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


# ── Citation-grounded quiz & flashcards ──────────────────────────────────────

@pytest.fixture
def app(settings, embedder):
    return create_app(settings, StudyBot(settings, embedder=embedder))


@pytest.fixture
def web(app):
    with TestClient(app) as client:
        yield client


def sign_up(web, username="alice"):
    response = web.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def seed_nodes(app, user_id: int, collection_name: str, node_specs: list[dict]) -> int:
    """Create a real collection + a dummy document row (to satisfy the FK) + OKF nodes for it,
    using the app's own store/okf_store so the study endpoints can see them. Returns collection_id."""
    store = app.state.store
    okf_store = app.state.okf_store
    collection_id = store.get_or_create_collection(collection_name, user_id)
    with store.transaction() as con:
        document_id = con.execute(
            "INSERT INTO documents (collection_id, title, source_type, source, sha256, chunk_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (collection_id, "Lecture 1", "pdf", "notes.pdf", "dummyhash", 0),
        ).lastrowid
    nodes = [OKFNode(source_document="Lecture 1", **spec) for spec in node_specs]
    embeddings = np.zeros((len(nodes), 4), dtype=np.float32)
    okf_store.insert_nodes(nodes, embeddings, document_id, collection_id, user_id)
    return collection_id


def fake_llm(monkeypatch, raw: str) -> None:
    async def stream(base_url, model, messages, **kwargs):
        yield ChatChunk(raw)
        yield ChatChunk("", True, eval_count=10, eval_seconds=1.0)

    monkeypatch.setattr(study_module, "chat_stream", stream)


ONE_NODE = [{"type": "concept", "title": "Gradient Descent",
            "description": "First-order optimisation.", "body": "Gradient descent minimises a differentiable function."}]


def test_quiz_resolves_valid_source(web, monkeypatch):
    user = sign_up(web)
    collection_id = seed_nodes(web.app, user["id"], "cv", ONE_NODE)
    fake_llm(monkeypatch, json.dumps([
        {"question": "What does gradient descent do?", "options": ["Minimise a function", "Sort a list"],
         "correct_index": 0, "explanation": "It minimises.", "source": 1},
    ]))
    res = web.post(f"/api/collections/{collection_id}/study/quiz", json={"num_questions": 1})
    assert res.status_code == 200, res.text
    source = res.json()["questions"][0]["source"]
    assert source["n"] == 1 and source["title"] == "Gradient Descent"


@pytest.mark.parametrize("bad_source", [99, 0, -1, "two", None])
def test_quiz_invalid_source_is_dropped(web, monkeypatch, bad_source):
    user = sign_up(web)
    collection_id = seed_nodes(web.app, user["id"], "cv", ONE_NODE)
    item = {"question": "Q?", "options": ["A", "B"], "correct_index": 0, "explanation": "E"}
    if bad_source is not None:
        item["source"] = bad_source
    fake_llm(monkeypatch, json.dumps([item]))
    res = web.post(f"/api/collections/{collection_id}/study/quiz", json={"num_questions": 1})
    assert res.status_code == 200, res.text
    assert res.json()["questions"][0]["source"] is None


def test_flashcards_resolves_source(web, monkeypatch):
    user = sign_up(web)
    collection_id = seed_nodes(web.app, user["id"], "cv", ONE_NODE)
    fake_llm(monkeypatch, json.dumps([
        {"front": "What does gradient descent do?", "back": "Minimises a function.", "tags": ["ml"], "source": 1},
    ]))
    res = web.post(f"/api/collections/{collection_id}/study/flashcards", json={"num_cards": 1})
    assert res.status_code == 200, res.text
    source = res.json()["cards"][0]["source"]
    assert source["n"] == 1 and source["title"] == "Gradient Descent"


def test_get_context_truncation_keeps_whole_nodes():
    """_get_context's character budget must select whole nodes, never slice one in half - a
    citation index that doesn't match what's actually in the prompt text would be unsound."""
    big_nodes = [
        OKFNode(node_id=i, type="concept", title=f"Node {i}", description="d",
               body="x" * 3000, source_document="doc") for i in range(1, 5)
    ]

    class FakeOKFStore:
        def list_nodes(self, **kwargs):
            return big_nodes

    request = types.SimpleNamespace(app=types.SimpleNamespace(
        state=types.SimpleNamespace(okf_store=FakeOKFStore())))
    context, included = study_module._get_context(request, collection_id=1, user_id=1)

    assert len(included) < len(big_nodes)  # budget (8000 chars) must have cut some nodes
    for i, node in enumerate(included, 1):
        assert f"[{i}] {node.title}" in context
        assert node.body in context  # whole body present, never sliced mid-node