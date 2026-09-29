import asyncio

import pytest

from app.core.ollama import ChatChunk, OllamaError
from app.rag import followup
from app.rag import pipeline as pipeline_module
from app.rag import prompt
from app.rag.pipeline import DoneEvent, QueryEvent, SourcesEvent, StudyBot, TokenEvent
from tests.fixtures import notes_docx

HISTORY = [("What is histogram equalization?", "It redistributes intensity values to improve contrast.")]


@pytest.mark.parametrize("question", [
    "What is its main limitation?", "And PNG?", "What about vector images?", "How does that compare with bicubic?",
    "Why does it over-segment?", "How is the second one different from the first?", "Explain it again", "More?",
    "Which one is more sensitive to noise?", "Which of the two is faster?", "Are both of them lossy?",
    "Is either better for photographs?",
])
def test_follow_ups_are_detected(question):
    assert followup.looks_like_follow_up(question)


@pytest.mark.parametrize("question", [
    "How does Otsu thresholding choose its threshold automatically from the image histogram?",
    "Explain the difference between raster and vector image storage in detail",
])
def test_self_contained_questions_are_left_alone(question):
    assert not followup.looks_like_follow_up(question)


def test_concat_uses_the_previous_question():
    assert followup.concat_query("What is its limit?", HISTORY) == "What is histogram equalization? What is its limit?"
    assert followup.concat_query("standalone", []) == "standalone"


@pytest.mark.parametrize("raw,expected", [
    ("What are the limitations of region growing?", "What are the limitations of region growing?"),
    ('"What is PNG?"', "What is PNG?"),
    ("Rewritten question: What is PNG?", "What is PNG?"),
    ("What is PNG?\nI hope that helps!", "What is PNG?"),
    ("", None), ("Sure", None), ("x " * 400, None),
])
def test_rewrite_output_is_cleaned_or_rejected(raw, expected):
    assert followup.clean_rewrite(raw, "And PNG?") == expected


def test_rewrite_prompt_carries_recent_turns_truncated():
    turns = [("q1", "a1"), ("q2", "b" * 900), ("q3", "a3")]
    messages = followup.rewrite_messages("and its limits?", turns)
    user = messages[1]["content"]
    assert "q1" not in user and "q2" in user and "q3" in user, "only the last two turns"
    assert "b" * 300 in user and "b" * 301 not in user, "long answers are truncated"
    assert user.rstrip().endswith("Rewritten question:")
    assert "Do not answer" in messages[0]["content"]


def stub_rewriter(monkeypatch, reply=None, error=None):
    calls = []

    async def stream(base_url, model, messages, **kwargs):
        calls.append(messages)
        if error:
            raise error
        yield ChatChunk(reply)
        yield ChatChunk("", True)

    monkeypatch.setattr(followup, "chat_stream", stream)
    return calls


def search(mode, question, history=HISTORY):
    return asyncio.run(followup.search_query(mode, question, history, base_url="http://x", model="m"))


def test_llm_mode_uses_the_models_standalone_question(monkeypatch):
    calls = stub_rewriter(monkeypatch, "What is the main limitation of histogram equalization?")
    assert search("llm", "What is its main limitation?") == "What is the main limitation of histogram equalization?"
    assert len(calls) == 1


def test_no_model_call_when_it_is_not_needed(monkeypatch):
    calls = stub_rewriter(monkeypatch, "should not be used")
    assert search("llm", "What is its main limitation?", history=[]) == "What is its main limitation?"
    assert search("off", "What is its main limitation?") == "What is its main limitation?"
    long_question = "How does Otsu thresholding choose its threshold automatically from the image histogram?"
    assert search("llm", long_question) == long_question
    assert calls == []


def test_concat_mode_needs_no_model(monkeypatch):
    calls = stub_rewriter(monkeypatch, "unused")
    assert search("concat", "And PNG?") == "What is histogram equalization? And PNG?" and calls == []


@pytest.mark.parametrize("reply,error", [(None, OllamaError("down")), ("Sure", None), ("", None)])
def test_a_failing_or_useless_model_falls_back_to_concat(monkeypatch, reply, error):
    stub_rewriter(monkeypatch, reply=reply or "", error=error)
    assert search("llm", "And PNG?") == "What is histogram equalization? And PNG?"


# ---- pipeline integration ----------------------------------------------------------------

@pytest.fixture
def bot(settings, embedder, tmp_path):
    settings.min_dense_score = 0.0
    bot = StudyBot(settings, embedder=embedder)
    bot.ingest(str(notes_docx(tmp_path / "Notes.docx")), "cv")
    return bot


def collect(bot, question, history):
    async def run():
        return [e async for e in bot.ask_stream(question, ["cv"], history=history)]
    return asyncio.run(run())


def stub_answerer(monkeypatch, text="Bicubic uses 16 pixels [1]."):
    seen = []

    async def stream(base_url, model, messages, **kwargs):
        seen.append(messages)
        yield ChatChunk(text)
        yield ChatChunk("", True)

    monkeypatch.setattr(pipeline_module, "chat_stream", stream)
    return seen


def test_a_follow_up_is_searched_by_its_rewrite_and_the_prompt_gets_the_conversation(bot, monkeypatch):
    stub_rewriter(monkeypatch, "How many pixels does bicubic interpolation use?")
    seen = stub_answerer(monkeypatch)
    searched = []
    real_search = bot.search
    monkeypatch.setattr(bot, "search", lambda q, *a, **k: (searched.append(q), real_search(q, *a, **k))[1])

    history = [("What is bicubic interpolation?", "A smooth resampling method.")]
    events = collect(bot, "And how many pixels does it use?", history)

    assert searched == ["How many pixels does bicubic interpolation use?"], "the rewrite is what gets searched"
    kinds = [type(e) for e in events]
    assert kinds[0] is QueryEvent and kinds[1] is SourcesEvent and kinds[-1] is DoneEvent and TokenEvent in kinds
    assert events[0].text == "How many pixels does bicubic interpolation use?"
    system, user = seen[0][0]["content"], seen[0][1]["content"]
    assert "Earlier in this conversation" in user and "What is bicubic interpolation?" in user
    assert user.rstrip().endswith("Question: And how many pixels does it use?"), "the model sees the real question"
    assert "only so you can tell what the question refers to" in system


def test_first_questions_and_independent_questions_are_not_rewritten(bot, monkeypatch):
    rewrites = stub_rewriter(monkeypatch, "unused")
    seen = stub_answerer(monkeypatch)
    events = collect(bot, "How many pixels does bicubic interpolation use?", [])
    assert not any(isinstance(e, QueryEvent) for e in events) and rewrites == []
    assert "Earlier in this conversation" not in seen[0][1]["content"]
    assert "only so you can tell" not in seen[0][0]["content"]

    long_independent = "How does bilinear interpolation estimate a pixel from the four nearest neighbours around it?"
    events = collect(bot, long_independent, [("What is Otsu?", "A thresholding method.")])
    assert not any(isinstance(e, QueryEvent) for e in events) and rewrites == []


def test_history_is_limited_to_the_configured_number_of_turns(bot, monkeypatch):
    stub_rewriter(monkeypatch, "What is interpolation?")
    seen = stub_answerer(monkeypatch)
    bot.settings.history_turns = 3
    many = [(f"question {i}", f"answer {i}") for i in range(8)]
    collect(bot, "and that?", many)
    user = seen[0][1]["content"]
    assert "question 7" in user and "question 6" in user, "prompt gets the last two turns"
    assert "question 5" not in user
