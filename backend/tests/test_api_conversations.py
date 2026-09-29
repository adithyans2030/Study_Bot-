"""Saved conversations over the API: creating, continuing, reopening, isolating and deleting chats."""
import json

import pytest

from app.core.ollama import OllamaError
from app.rag import pipeline as pipeline_module
from tests.fixtures import notes_docx
from tests.test_api import (PASSWORD, app, event, fake_llm, sign_in_as, sign_up, sse, upload_ok,  # noqa: F401
                            web)


@pytest.fixture
def library(web, tmp_path):
    sign_up(web)
    upload_ok(web, notes_docx(tmp_path / "n.docx").read_bytes(), name="Interpolation Notes.docx")
    return web


def ask(web, question, conversation_id=None, collections=None):
    body = {"question": question}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    if collections:
        body["collections"] = collections
    return sse(web.post("/api/chat", json=body))


def test_first_question_creates_a_saved_chat_that_can_be_reopened(library, monkeypatch):
    fake_llm(monkeypatch, "Bicubic uses 16 pixels [1] and more [9].")
    events = ask(library, "How many pixels does bicubic interpolation use?")
    conversation = event(events, "conversation")
    assert conversation["title"] == "How many pixels does bicubic interpolation use?"

    (listed,) = library.get("/api/conversations").json()
    assert listed["id"] == conversation["id"] and listed["title"] == conversation["title"]

    saved = library.get(f"/api/conversations/{conversation['id']}").json()
    user_message, answer = saved["messages"]
    assert user_message["role"] == "user" and user_message["content"] == "How many pixels does bicubic interpolation use?"
    assert answer["role"] == "assistant"
    assert "[9]" not in answer["content"], "the saved answer is the cleaned text"
    assert answer["meta"]["cited"] == [1] and answer["meta"]["invalid_citations"] == 1
    assert answer["sources"][0]["title"] == "Interpolation Notes", "sources are saved so the chat reopens as it was"


def test_a_follow_up_joins_the_same_chat_and_is_searched_with_context(library, monkeypatch):
    fake_llm(monkeypatch, "Bicubic uses 16 pixels [1].")
    first = ask(library, "How many pixels does bicubic interpolation use?")
    conversation_id = event(first, "conversation")["id"]

    prompts = []
    fake_llm(monkeypatch, "It is smoother than bilinear [1].", prompts)
    second = ask(library, "And how does it compare with bilinear?", conversation_id)

    assert event(second, "conversation")["id"] == conversation_id
    query = event(second, "query")["text"]
    assert "bicubic" in query.lower() and "compare with bilinear" in query, "the follow-up was searched with its context"
    user_prompt = prompts[0][1]["content"]
    assert "Earlier in this conversation" in user_prompt and "How many pixels does bicubic" in user_prompt
    assert user_prompt.rstrip().endswith("Question: And how does it compare with bilinear?")

    messages = library.get(f"/api/conversations/{conversation_id}").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[3]["meta"]["search_query"] == query
    assert len(library.get("/api/conversations").json()) == 1


def test_an_independent_question_in_a_chat_is_not_rewritten(library, monkeypatch):
    fake_llm(monkeypatch, "ok [1]")
    conversation_id = event(ask(library, "What is bicubic interpolation?"), "conversation")["id"]
    events = ask(library, "How does bilinear interpolation estimate a pixel from the four nearest neighbours around it?",
                 conversation_id)
    assert "query" not in [n for n, _ in events]


def test_chats_are_listed_newest_first_and_can_be_deleted(library, monkeypatch):
    fake_llm(monkeypatch, "ok [1]")
    old = event(ask(library, "first chat about bicubic"), "conversation")["id"]
    new = event(ask(library, "second chat about bilinear"), "conversation")["id"]
    ask(library, "one more question here about interpolation", old)  # touching the old chat moves it to the top
    assert [c["id"] for c in library.get("/api/conversations").json()] == [old, new]
    assert library.delete(f"/api/conversations/{new}").status_code == 204
    assert library.get(f"/api/conversations/{new}").status_code == 404
    assert library.delete(f"/api/conversations/{new}").status_code == 404
    assert [c["id"] for c in library.get("/api/conversations").json()] == [old]


def test_other_users_cannot_read_continue_or_delete_a_chat(library, app, monkeypatch):
    fake_llm(monkeypatch, "secret answer [1]")
    conversation_id = event(ask(library, "alice's private question about bicubic"), "conversation")["id"]
    app.state.settings.allow_registration = True
    library.cookies.clear()
    sign_up(library, "bob")

    assert library.get("/api/conversations").json() == []
    assert library.get(f"/api/conversations/{conversation_id}").status_code == 404
    assert library.delete(f"/api/conversations/{conversation_id}").status_code == 404
    hijack = library.post("/api/chat", json={"question": "hello", "conversation_id": conversation_id})
    assert hijack.status_code == 404

    sign_in_as(library, "alice")
    messages = library.get(f"/api/conversations/{conversation_id}").json()["messages"]
    assert [m["content"] for m in messages if m["role"] == "user"] == ["alice's private question about bicubic"]
    assert len(messages) == 2, "nothing was appended by the other user"


def test_a_question_with_no_materials_is_still_saved(web):
    sign_up(web)
    events = ask(web, "anything at all?")
    conversation_id = event(events, "conversation")["id"]
    messages = web.get(f"/api/conversations/{conversation_id}").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["meta"]["refused"] is True and "haven't added" in messages[1]["content"]


def test_a_failed_answer_keeps_the_question_but_saves_no_answer(library, monkeypatch):
    async def down(base_url, model, messages, **kwargs):
        raise OllamaError("Cannot reach Ollama")
        yield  # pragma: no cover

    monkeypatch.setattr(pipeline_module, "chat_stream", down)
    events = ask(library, "how many pixels does bicubic use")
    assert events[-1][0] == "error"
    messages = library.get(f"/api/conversations/{event(events, 'conversation')['id']}").json()["messages"]
    assert [m["role"] for m in messages] == ["user"]


def test_refusals_do_not_pollute_the_history_used_for_follow_ups(library, app, monkeypatch):
    app.state.settings.min_dense_score = 0.99  # everything is refused by the gate
    conversation_id = event(ask(library, "what is the capital of France"), "conversation")["id"]
    app.state.settings.min_dense_score = 0.0
    prompts = []
    fake_llm(monkeypatch, "ok [1]", prompts)
    ask(library, "and its population?", conversation_id)
    assert "Earlier in this conversation" not in prompts[0][1]["content"], "a refused exchange says nothing about the topic"


def test_conversation_endpoints_require_sign_in_and_validate_ids(web, library):
    web.cookies.clear()
    assert web.get("/api/conversations").status_code == 401
    assert web.get("/api/conversations/1").status_code == 401
    assert web.post("/api/chat", json={"question": "hi", "conversation_id": 1}).status_code == 401
    sign_in_as(web, "alice")
    assert web.get("/api/conversations/99999").status_code == 404
    assert web.post("/api/chat", json={"question": "hi", "conversation_id": 99999}).status_code == 404
    assert json.loads(web.get("/api/conversations").text) == []
