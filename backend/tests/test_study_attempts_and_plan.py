"""Tests for quiz attempt history and the exam-driven study planner (Phase 5)."""
from datetime import date, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.okf.models import OKFNode
from app.rag.pipeline import StudyBot
from app.rag.store import Store
from app.study.attempts_store import AttemptsStore, NodeAttemptStats
from app.study.planner import build_plan

PASSWORD = "correct horse battery"
ONE_NODE = [{"type": "concept", "title": "Gradient Descent",
            "description": "First-order optimisation.", "body": "Gradient descent minimises a differentiable function."}]


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
    """Create a real collection + a dummy document row (to satisfy the FK) + OKF nodes for it."""
    store = app.state.store
    okf_store = app.state.okf_store
    collection_id = store.get_or_create_collection(collection_name, user_id)
    with store.transaction() as con:
        document_id = con.execute(
            "INSERT INTO documents (collection_id, title, source_type, source, sha256, chunk_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (collection_id, "Lecture 1", "pdf", "notes.pdf", "dummyhash", 0),
        ).lastrowid
    import numpy as np
    nodes = [OKFNode(source_document="Lecture 1", **spec) for spec in node_specs]
    embeddings = np.zeros((len(nodes), 4), dtype="float32")
    okf_store.insert_nodes(nodes, embeddings, document_id, collection_id, user_id)
    return collection_id


# ── AttemptsStore ─────────────────────────────────────────────────────────────

def test_attempts_store_node_stats(tmp_path):
    store = Store(tmp_path / "studybot.db")
    attempts = AttemptsStore(store)

    attempts.record_attempts(user_id=1, collection_id=1, rows=[(10, True), (10, False), (10, True)])
    attempts.record_attempts(user_id=1, collection_id=1, rows=[(999, True)])  # orphan: no such live node

    stats = attempts.node_stats(collection_id=1, user_id=1)
    assert stats[10].attempts == 3
    assert stats[10].correct == 2
    assert stats[10].accuracy == pytest.approx(2 / 3)
    # The orphan id is recorded and aggregated fine - there's no FK to reject it. "Orphan safety"
    # is the planner's job (it only ever looks up ids from the live node list), not the store's.
    assert stats[999].attempts == 1


def test_record_quiz_attempts_endpoint(web):
    user = sign_up(web)
    collection_id = seed_nodes(web.app, user["id"], "cv", ONE_NODE)
    node_id = web.app.state.okf_store.list_nodes(collection_id=collection_id, user_id=user["id"])[0].node_id

    res = web.post(f"/api/collections/{collection_id}/study/quiz/attempts", json={
        "attempts": [{"node_id": node_id, "correct": True}, {"node_id": None, "correct": False}],
    })
    assert res.status_code == 200, res.text
    assert res.json()["recorded"] == 2

    stats = web.app.state.attempts_store.node_stats(collection_id, user["id"])
    assert stats[node_id].attempts == 1 and stats[node_id].correct == 1


# ── planner.build_plan (pure, no DB/HTTP) ────────────────────────────────────

def test_build_plan_orders_untested_then_weak_then_known():
    untested = OKFNode(node_id=1, type="concept", title="Untested", description="d", body="b", source_document="doc")
    weak = OKFNode(node_id=2, type="concept", title="Weak", description="d", body="b", source_document="doc")
    known = OKFNode(node_id=3, type="concept", title="Known", description="d", body="b", source_document="doc")
    stats = {
        2: NodeAttemptStats(attempts=3, correct=1, accuracy=1 / 3, last_attempt_at=100.0),
        3: NodeAttemptStats(attempts=3, correct=3, accuracy=1.0, last_attempt_at=100.0),
    }
    today = date(2026, 10, 1)

    plan = build_plan([known, weak, untested], stats, today, today)  # today == deadline -> one bucket

    assert len(plan.days) == 1
    assert [n.title for n in plan.days[0].nodes] == ["Untested", "Weak", "Known"]
    assert [n.status for n in plan.days[0].nodes] == ["untested", "weak", "known"]


# ── GET /plan endpoint ────────────────────────────────────────────────────────

def test_plan_endpoint_rejects_past_deadline(web):
    user = sign_up(web)
    collection_id = seed_nodes(web.app, user["id"], "cv", ONE_NODE)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    res = web.get(f"/api/collections/{collection_id}/study/plan", params={"deadline": yesterday})
    assert res.status_code == 422


def test_plan_endpoint_handles_deadline_today(web):
    user = sign_up(web)
    collection_id = seed_nodes(web.app, user["id"], "cv", ONE_NODE)
    today = date.today().isoformat()
    res = web.get(f"/api/collections/{collection_id}/study/plan", params={"deadline": today})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["days_remaining"] == 0
    assert len(body["days"]) == 1  # no divide-by-zero, single bucket
    assert body["days"][0]["nodes"][0]["status"] == "untested"


def test_plan_endpoint_no_attempts_yet(web):
    user = sign_up(web)
    collection_id = seed_nodes(web.app, user["id"], "cv", ONE_NODE)
    deadline = (date.today() + timedelta(days=7)).isoformat()
    res = web.get(f"/api/collections/{collection_id}/study/plan", params={"deadline": deadline})
    assert res.status_code == 200, res.text
    body = res.json()
    all_nodes = [n for day in body["days"] for n in day["nodes"]]
    assert all_nodes and all(n["status"] == "untested" for n in all_nodes)
