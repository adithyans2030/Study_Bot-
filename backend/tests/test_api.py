"""End-to-end tests of the web API: auth, uploads, indexing jobs, isolation and chat."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.core.ollama import ChatChunk, OllamaError
from app.ingest.types import LoadedDocument, Segment
from app.main import create_app
from app.rag import pipeline as pipeline_module
from app.rag.pipeline import StudyBot
from tests.fixtures import notes_docx, notes_pdf

PASSWORD = "correct horse battery"


@pytest.fixture
def app(settings, embedder):
    settings.followup_mode = "concat"  # deterministic: no model call to rewrite follow-ups in tests
    settings.min_dense_score = 0.0  # the hashing test embedder's cosines are not comparable to a real model's
    return create_app(settings, StudyBot(settings, embedder=embedder))


@pytest.fixture
def web(app):
    with TestClient(app) as client:
        yield client


def sign_up(web, username="alice"):
    response = web.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def sign_in_as(web, username):
    web.cookies.clear()
    response = web.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text


def wait_for(web, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = web.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish: {job}")


def upload(web, data: bytes, name="Unit 1 notes.pdf", collection="cv"):
    return web.post("/api/documents", files={"file": (name, data, "application/octet-stream")},
                    data={"collection": collection})


def upload_ok(web, data: bytes, name="Unit 1 notes.pdf", collection="cv"):
    response = upload(web, data, name, collection)
    assert response.status_code == 202, response.text
    job = wait_for(web, response.json()["id"])
    assert job["status"] == "done", job
    return job


def sse(response) -> list[tuple[str, object]]:
    events = []
    for block in response.text.split("\n\n"):
        lines = [ln for ln in block.splitlines() if not ln.startswith(":")]
        if not lines:
            continue
        name = next(ln[7:] for ln in lines if ln.startswith("event: "))
        data = json.loads(next(ln[6:] for ln in lines if ln.startswith("data: ")))
        events.append((name, data))
    return events


def event(events, name):
    """The data of the first event called `name`."""
    return next(data for n, data in events if n == name)


# ---- auth --------------------------------------------------------------------------------

def test_first_registration_signs_you_in_with_a_hardened_cookie(web):
    assert web.get("/api/auth/status").json() == {"has_users": False, "registration_open": True, "user": None}
    response = web.post("/api/auth/register", json={"username": "Alice", "password": PASSWORD})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "alice", "is_admin": True}
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "studybot_session=" in cookie
    assert web.get("/api/auth/me").json()["username"] == "alice"
    status = web.get("/api/auth/status").json()
    assert status["has_users"] and not status["registration_open"] and status["user"]["username"] == "alice"
    web.cookies.clear()
    assert web.get("/api/auth/status").json()["user"] is None, "signed-out visitors see no user"


def test_registration_is_closed_after_the_first_account_unless_enabled(web, app):
    sign_up(web)
    web.cookies.clear()
    closed = web.post("/api/auth/register", json={"username": "bob", "password": PASSWORD})
    assert closed.status_code == 403 and "closed" in closed.json()["detail"]
    app.state.settings.allow_registration = True
    opened = web.post("/api/auth/register", json={"username": "bob", "password": PASSWORD})
    assert opened.status_code == 201 and opened.json()["is_admin"] is False


@pytest.mark.parametrize("payload", [
    {"username": "ab", "password": PASSWORD}, {"username": "alice", "password": "short"},
    {"username": "bad name", "password": PASSWORD},
])
def test_registration_validates_input(web, payload):
    assert web.post("/api/auth/register", json=payload).status_code == 422


def test_login_failures_are_generic_and_rate_limited(web):
    sign_up(web)
    web.cookies.clear()
    wrong = web.post("/api/auth/login", json={"username": "alice", "password": "nope nope nope"})
    unknown = web.post("/api/auth/login", json={"username": "nobody", "password": "nope nope nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json(), "must not reveal which usernames exist"
    for _ in range(4):
        web.post("/api/auth/login", json={"username": "alice", "password": "nope nope nope"})
    blocked = web.post("/api/auth/login", json={"username": "alice", "password": PASSWORD})
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0, "even the right password waits"


def test_logout_invalidates_the_session_server_side(web):
    sign_up(web)
    stolen = web.cookies.get("studybot_session")
    assert web.post("/api/auth/logout").status_code == 204
    assert web.get("/api/auth/me").status_code == 401
    web.cookies.set("studybot_session", stolen)
    assert web.get("/api/auth/me").status_code == 401, "the old token must be dead, not just deleted client-side"


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/auth/me", None), ("get", "/api/collections", None), ("get", "/api/documents", None),
    ("get", "/api/jobs", None), ("get", "/api/jobs/abc", None), ("delete", "/api/documents/1", None),
    ("post", "/api/documents/youtube", {"url": "https://youtu.be/tVskbekONlw"}),
    ("post", "/api/chat", {"question": "hi"}),
])
def test_everything_private_requires_sign_in(web, method, path, body):
    response = getattr(web, method)(path, **({"json": body} if body else {}))
    assert response.status_code == 401


def test_cross_site_writes_are_blocked_but_same_origin_and_scripts_work(web):
    sign_up(web)
    forged = web.post("/api/collections", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert forged.status_code == 403
    same = web.post("/api/collections", json={"name": "x"}, headers={"Origin": "http://testserver"})
    assert same.status_code == 201
    assert web.post("/api/collections", json={"name": "y"}).status_code == 201, "no Origin header (curl) is fine"


def test_security_headers(web):
    home = web.get("/")
    assert home.status_code == 200
    csp = home.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    # style-src allows inline (Radix Primitives position tooltips/popovers/selects with
    # JS-computed inline styles); script-src does not relax at all — that's the one that
    # actually matters for XSS. See core/security.py.
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "script-src 'self';" in csp and "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert home.headers["x-content-type-options"] == "nosniff" and home.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" not in web.get("/docs").headers, "Swagger UI needs inline scripts"
    assert web.get("/api/health").headers["x-content-type-options"] == "nosniff"


# ---- uploads and indexing jobs -----------------------------------------------------------

def test_upload_is_indexed_in_the_background_and_listed(web, app, tmp_path):
    sign_up(web)
    data = notes_pdf(tmp_path / "n.pdf").read_bytes()
    response = upload(web, data)
    assert response.status_code == 202
    job = response.json()
    assert job["status"] in ("pending", "running", "done") and "source" not in job

    finished = wait_for(web, job["id"])
    assert finished["status"] == "done" and finished["chunks"] >= 1 and finished["document_id"]

    (doc,) = web.get("/api/documents").json()
    assert doc["title"] == "Unit 1 notes" and doc["type"] == "pdf" and doc["collection"] == "cv"
    assert "uploads" not in json.dumps(doc) and doc["url"] is None, "server paths must never reach the browser"
    stored = list((app.state.settings.uploads_dir / "1").iterdir())
    assert len(stored) == 1 and stored[0].suffix == ".pdf" and "notes" not in stored[0].name
    assert web.get(f"/api/documents/{doc['id']}").json()["id"] == doc["id"]
    assert [c["name"] for c in web.get("/api/collections").json()] == ["cv"]


def test_job_progress_stream_ends_with_the_final_state(web, tmp_path):
    sign_up(web)
    job = upload(web, notes_pdf(tmp_path / "n.pdf").read_bytes()).json()
    with web.stream("GET", f"/api/jobs/{job['id']}/events") as stream:
        body = "".join(stream.iter_text())
    events = [json.loads(ln[6:]) for ln in body.splitlines() if ln.startswith("data: ")]
    assert events and events[-1]["status"] == "done"
    assert all(e["id"] == job["id"] for e in events)


def test_type_is_decided_by_contents_not_by_filename(web, tmp_path):
    sign_up(web)
    job = upload_ok(web, notes_docx(tmp_path / "n.docx").read_bytes(), name="actually-a-word-file.pdf")
    (doc,) = web.get("/api/documents").json()
    assert doc["type"] == "docx" and job["status"] == "done"


@pytest.mark.parametrize("data,name,status,message", [
    (b"just some text", "evil.pdf", 415, "Unsupported"),
    (b"", "empty.pdf", 400, "empty"),
    (b"\xd0\xcf\x11\xe0" + b"\0" * 200, "old.doc", 400, "Old .doc"),
])
def test_bad_uploads_are_rejected_with_a_reason_and_leave_nothing_behind(web, app, data, name, status, message):
    sign_up(web)
    response = upload(web, data, name)
    assert response.status_code == status and message in response.json()["detail"]
    folder = app.state.settings.uploads_dir / "1"
    assert not folder.exists() or list(folder.iterdir()) == []
    assert web.get("/api/jobs").json() == []


def test_oversized_uploads_are_rejected(web, app):
    sign_up(web)
    app.state.settings.max_upload_mb = 1
    response = upload(web, b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024))
    assert response.status_code == 413 and "too large" in response.json()["detail"]
    folder = app.state.settings.uploads_dir / "1"
    assert not folder.exists() or list(folder.iterdir()) == []


def test_a_file_that_cannot_be_read_fails_the_job_cleanly(web, app):
    sign_up(web)
    response = upload(web, b"%PDF-1.4\n" + b"garbage " * 200, name="broken.pdf")
    assert response.status_code == 202
    job = wait_for(web, response.json()["id"])
    assert job["status"] == "failed" and job["error"] and "Traceback" not in job["error"]
    assert "uploads" not in job["error"] and str(app.state.settings.home) not in job["error"], "no server paths"
    assert "broken" in job["error"], "the message names the file by the user's own name, not the stored random one"
    assert list((app.state.settings.uploads_dir / "1").iterdir()) == [], "unreadable uploads are not kept"
    assert web.get("/api/documents").json() == []


def test_uploading_the_same_content_twice_does_not_duplicate_it(web, app, tmp_path):
    sign_up(web)
    data = notes_pdf(tmp_path / "n.pdf").read_bytes()
    upload_ok(web, data, name="first.pdf")
    second = upload_ok(web, data, name="second copy.pdf")
    assert any("already had this exact file" in w for w in second["warnings"])
    assert len(web.get("/api/documents").json()) == 1
    assert len(list((app.state.settings.uploads_dir / "1").iterdir())) == 1


def fake_video_loader(monkeypatch):
    def load(url, cache_dir=None):
        segments = [Segment(f"caption number {i} about mlflow tracking runs", t_start=i * 4.0, t_end=i * 4.0 + 4)
                    for i in range(40)]
        return LoadedDocument("A Lecture", "youtube", "https://www.youtube.com/watch?v=tVskbekONlw", "vh", segments)
    monkeypatch.setattr("app.ingest.loader.load_youtube", load)


def test_youtube_links_are_validated_then_indexed(web, monkeypatch):
    sign_up(web)
    assert web.post("/api/documents/youtube", json={"url": "https://vimeo.com/123"}).status_code == 422
    assert web.post("/api/documents/youtube", json={"url": "https://internal.host/x"}).status_code == 422
    assert web.post("/api/documents/youtube", json={"url": "https://www.youtube.com/watch"}).status_code == 422
    fake_video_loader(monkeypatch)
    response = web.post("/api/documents/youtube",
                        json={"url": "https://youtu.be/tVskbekONlw?t=30&list=PPSV", "collection": "mlops"})
    assert response.status_code == 202
    assert wait_for(web, response.json()["id"])["status"] == "done"
    (doc,) = web.get("/api/documents", params={"collection": "mlops"}).json()
    assert doc["type"] == "youtube" and doc["url"] == "https://www.youtube.com/watch?v=tVskbekONlw"


def test_delete_document_removes_index_entries_and_the_stored_file(web, app, tmp_path):
    sign_up(web)
    upload_ok(web, notes_pdf(tmp_path / "n.pdf").read_bytes())
    (doc,) = web.get("/api/documents").json()
    assert app.state.bot.search("sobel operator", ["cv"], user_id=1).hits

    assert web.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert web.get(f"/api/documents/{doc['id']}").status_code == 404
    assert web.delete(f"/api/documents/{doc['id']}").status_code == 404
    assert app.state.bot.search("sobel operator", ["cv"], user_id=1).hits == []
    assert list((app.state.settings.uploads_dir / "1").iterdir()) == []


def test_reindex_keeps_the_title(web, tmp_path):
    sign_up(web)
    upload_ok(web, notes_pdf(tmp_path / "n.pdf").read_bytes(), name="My Lecture Notes.pdf")
    (doc,) = web.get("/api/documents").json()
    job = web.post(f"/api/documents/{doc['id']}/reindex").json()
    assert wait_for(web, job["id"])["status"] == "done"
    (after,) = web.get("/api/documents").json()
    assert after["title"] == "My Lecture Notes" and after["id"] != doc["id"] or after["title"] == "My Lecture Notes"


def test_collections_can_be_created_validated_and_deleted_with_their_files(web, app, tmp_path):
    sign_up(web)
    assert web.post("/api/collections", json={"name": "Physics 101"}).status_code == 201
    assert web.post("/api/collections", json={"name": "Physics 101"}).status_code == 201, "idempotent"
    assert web.post("/api/collections", json={"name": "<script>"}).status_code == 422
    assert web.post("/api/collections", json={"name": ""}).status_code == 422
    upload_ok(web, notes_pdf(tmp_path / "n.pdf").read_bytes(), collection="Physics 101")
    (physics,) = [c for c in web.get("/api/collections").json() if c["name"] == "Physics 101"]
    assert physics["documents"] == 1
    assert web.delete(f"/api/collections/{physics['id']}").status_code == 204
    assert web.get("/api/collections").json() == []
    assert web.get("/api/documents").json() == []
    assert list((app.state.settings.uploads_dir / "1").iterdir()) == []


# ---- isolation between users -------------------------------------------------------------

def test_users_cannot_see_touch_or_search_each_others_material(web, app, tmp_path):
    sign_up(web, "alice")
    app.state.settings.allow_registration = True
    alice_job = upload_ok(web, notes_docx(tmp_path / "a.docx").read_bytes(), name="Alice Secret Notes.docx")
    (alice_doc,) = web.get("/api/documents").json()
    (alice_coll,) = web.get("/api/collections").json()

    web.cookies.clear()
    sign_up(web, "bob")
    assert web.get("/api/documents").json() == [] and web.get("/api/collections").json() == []
    assert web.get(f"/api/documents/{alice_doc['id']}").status_code == 404
    assert web.delete(f"/api/documents/{alice_doc['id']}").status_code == 404
    assert web.post(f"/api/documents/{alice_doc['id']}/reindex").status_code == 404
    assert web.delete(f"/api/collections/{alice_coll['id']}").status_code == 404
    assert web.get(f"/api/jobs/{alice_job['id']}").status_code == 404
    assert web.get(f"/api/jobs/{alice_job['id']}/events").status_code == 404
    assert web.get("/api/jobs").json() == []

    chat = sse(web.post("/api/chat", json={"question": "interpolation bicubic pixels"}))
    assert chat[-1][1]["refused"] and "haven't added" in chat[-1][1]["text"], "bob has no materials"
    assert web.post("/api/chat", json={"question": "x", "collections": ["cv"]}).status_code == 404

    # same collection name, separate data; bob's searches never surface alice's document
    upload_ok(web, notes_pdf(tmp_path / "b.pdf").read_bytes(), name="Bob Notes.pdf")
    events = sse(web.post("/api/chat", json={"question": "interpolation bicubic pixels", "collections": ["cv"]}))
    titles = {s["title"] for s in event(events, "sources")}
    assert "Alice Secret Notes" not in titles

    sign_in_as(web, "alice")
    assert [d["title"] for d in web.get("/api/documents").json()] == ["Alice Secret Notes"]
    assert web.get(f"/api/documents/{alice_doc['id']}").status_code == 200


# ---- chat --------------------------------------------------------------------------------

def fake_llm(monkeypatch, text, calls=None):
    async def stream(base_url, model, messages, **kwargs):
        if calls is not None:
            calls.append(messages)
        for i in range(0, len(text), 8):
            yield ChatChunk(text[i:i + 8])
        yield ChatChunk("", True, eval_count=10, eval_seconds=1.0, prompt_tokens=100, prompt_seconds=1.0)
    monkeypatch.setattr(pipeline_module, "chat_stream", stream)


@pytest.fixture
def library(web, tmp_path):
    sign_up(web)
    upload_ok(web, notes_docx(tmp_path / "n.docx").read_bytes(), name="Interpolation Notes.docx")
    return web


def test_chat_streams_sources_then_tokens_then_a_cleaned_final_answer(library, monkeypatch):
    raw = "Bicubic uses 16 pixels [1] and also something else [7]."
    fake_llm(monkeypatch, raw)
    response = library.post("/api/chat", json={"question": "how many pixels does bicubic use", "collections": ["cv"]})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    events = sse(response)
    names = [n for n, _ in events]
    assert names[:2] == ["conversation", "sources"] and names[-1] == "done" and set(names[2:-1]) == {"token"}
    assert "".join(d["text"] for n, d in events if n == "token") == raw, "the stream is the raw model output"

    done = events[-1][1]
    assert done["text"] == "Bicubic uses 16 pixels [1] and also something else ." or "[7]" not in done["text"]
    assert done["cited"] == [1] and done["invalid_citations"] == 1
    assert not done["refused"] and not done["gated"] and not done["empty"]

    (source,) = event(events, "sources")
    assert set(source) == {"n", "title", "type", "location", "url", "header", "snippet"}
    assert source["n"] == 1 and source["title"] == "Interpolation Notes" and len(source["snippet"]) <= 400
    assert "uploads" not in json.dumps(event(events, "sources")), "no server paths in sources"


def test_chat_flags_answers_that_are_only_citations(library, monkeypatch):
    fake_llm(monkeypatch, "[1]")
    done = sse(library.post("/api/chat", json={"question": "bicubic pixels"}))[-1][1]
    assert done["empty"] is True and done["cited"] == [1]


def test_low_relevance_questions_are_stopped_before_the_model_is_called(library, app, monkeypatch):
    calls = []
    fake_llm(monkeypatch, "should never appear", calls)
    app.state.settings.min_dense_score = 0.99
    events = sse(library.post("/api/chat", json={"question": "what is the capital of France"}))
    assert [n for n, _ in events] == ["conversation", "sources", "done"]
    done = events[-1][1]
    assert done["gated"] and done["refused"] and "couldn't find" in done["text"] and calls == []


def test_chat_input_validation(library):
    assert library.post("/api/chat", json={"question": ""}).status_code == 422
    assert library.post("/api/chat", json={"question": "x" * 2001}).status_code == 422
    assert library.post("/api/chat", json={"question": "hi", "collections": ["nope"]}).status_code == 404
    assert library.post("/api/chat", json={}).status_code == 422


def test_model_problems_become_a_clean_error_event(library, monkeypatch):
    async def down(base_url, model, messages, **kwargs):
        raise OllamaError("Cannot reach Ollama at http://x. Is it running?")
        yield  # pragma: no cover  (makes this an async generator)
    monkeypatch.setattr(pipeline_module, "chat_stream", down)
    events = sse(library.post("/api/chat", json={"question": "bicubic pixels"}))
    assert events[-1][0] == "error" and "Cannot reach Ollama" in events[-1][1]["message"]

    async def crash(base_url, model, messages, **kwargs):
        raise RuntimeError("secret internal detail /home/x/y.py")
        yield  # pragma: no cover
    monkeypatch.setattr(pipeline_module, "chat_stream", crash)
    events = sse(library.post("/api/chat", json={"question": "bicubic pixels"}))
    assert events[-1][0] == "error" and "secret internal detail" not in events[-1][1]["message"]


def test_prompt_treats_documents_as_data_and_the_chat_path_has_no_tools(library, monkeypatch):
    calls = []
    fake_llm(monkeypatch, "ok [1]", calls)
    library.post("/api/chat", json={"question": "bicubic pixels"})
    system = calls[0][0]["content"]
    assert "not instructions" in system and calls[0][1]["role"] == "user"
    assert len(calls[0]) == 2, "only a system and a user message; no tools are offered to the model"
