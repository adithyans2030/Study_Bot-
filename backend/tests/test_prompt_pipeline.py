import asyncio
import json

import httpx
import pytest

from app.core import ollama
from app.core.ollama import ChatChunk, OllamaError, chat_stream
from app.ingest.types import IngestError
from app.rag import pipeline as pipeline_module
from app.rag import prompt
from app.rag.pipeline import StudyBot
from app.rag.retrieve import Hit
from app.rag.store import ChunkRecord
from tests.fixtures import notes_docx


def hit(text="Sobel is first order.", source_type="pdf", **meta):
    chunk = ChunkRecord(1, 1, "Unit 2 Notes", source_type, "src", 0, "Unit 2 Notes › 6. Sobel", text, meta)
    return Hit(chunk, 0.5, 0.7)


# ---- prompt ------------------------------------------------------------------------------

def test_location_labels():
    assert prompt.location(hit(page_start=3, page_end=3)) == "p.3"
    assert prompt.location(hit(page_start=3, page_end=5)) == "pp.3-5"
    assert prompt.location(hit(slide=4)) == "slide 4"
    assert prompt.location(hit(t_start=754.2)) == "12:34"
    assert prompt.location(hit(t_start=3725)) == "1:02:05"
    assert prompt.location(hit()) == ""


def test_source_url_deep_links_youtube_only():
    yt = hit(source_type="youtube", t_start=90.7)
    assert prompt.source_url(yt) == "src&t=90s"
    assert prompt.source_url(hit(page_start=1, page_end=1)) is None


def test_build_messages_numbers_sources_and_includes_question():
    messages = prompt.build_messages("What is Sobel?", [hit(page_start=2, page_end=2), hit("Laplacian text", page_start=3, page_end=3)])
    assert messages[0]["role"] == "system" and prompt.REFUSAL in messages[0]["content"]
    user = messages[1]["content"]
    assert "[1] Unit 2 Notes (p.2)" in user and "[2] Unit 2 Notes (p.3)" in user
    assert user.rstrip().endswith("Question: What is Sobel?")


def test_extract_citations_keeps_valid_drops_invalid():
    text, cited, invalid = prompt.extract_citations("Sobel is first order [1]. It is directional [2, 5] and old [9].", 3)
    assert cited == [1, 2] and invalid == 2
    assert "[5]" not in text and "[9]" not in text and "[1]" in text and "[2]" in text


def test_extract_citations_no_markers():
    assert prompt.extract_citations("No citations here.", 3) == ("No citations here.", [], 0)


def test_is_empty_answer_detects_citation_only_output():
    assert prompt.is_empty_answer("[2][5][6]")
    assert prompt.is_empty_answer("  [1]. ")
    assert prompt.is_empty_answer("")
    assert not prompt.is_empty_answer("It is 256 [1]")
    assert not prompt.is_empty_answer("Sobel is first order [1].")


def test_ask_flags_a_citation_only_answer_as_empty(bot, tmp_path, monkeypatch):
    bot.ingest(str(notes_docx(tmp_path / "Notes.docx")), "cv")
    fake_llm(monkeypatch, "[1][2]")
    answer = asyncio.run(bot.ask("interpolation", ["cv"]))
    assert answer.empty
    assert answer.cited == [1] and answer.invalid_citations == 1  # only one chunk exists, so [2] is dropped


def test_is_refusal_tolerates_case_and_punctuation():
    assert prompt.is_refusal("I couldn't find that in your study materials.")
    assert prompt.is_refusal("i couldn't find that in your study materials")
    assert not prompt.is_refusal("Sobel is first order [1].")


# ---- ollama streaming --------------------------------------------------------------------

def patch_transport(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(ollama.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def collect(**kwargs):
    async def run():
        return [c async for c in chat_stream("http://ollama", "m", [{"role": "user", "content": "hi"}], **kwargs)]
    return asyncio.run(run())


def test_chat_stream_yields_tokens_then_stats(monkeypatch):
    body = "\n".join(json.dumps(x) for x in [
        {"message": {"content": "Hel"}}, {"message": {"content": "lo"}},
        {"message": {"content": ""}, "done": True, "eval_count": 2, "eval_duration": 1_000_000_000}]) + "\n"
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, content=body.encode())

    patch_transport(monkeypatch, handler)
    chunks = collect(num_ctx=4096)
    assert "".join(c.text for c in chunks) == "Hello"
    assert chunks[-1].done and chunks[-1].eval_count == 2 and chunks[-1].eval_seconds == 1.0
    assert seen["options"]["num_ctx"] == 4096 and seen["stream"] is True


def test_chat_stream_surfaces_model_not_found(monkeypatch):
    patch_transport(monkeypatch, lambda r: httpx.Response(404, json={"error": "model 'nope' not found"}))
    with pytest.raises(OllamaError, match="model 'nope' not found"):
        collect()


def test_chat_stream_timeout_is_a_friendly_error_not_a_traceback(monkeypatch):
    """Regression: a slow Ollama used to surface as a raw httpx.ConnectTimeout and kill a 20-minute eval."""
    def handler(request):
        raise httpx.ConnectTimeout("timed out")
    patch_transport(monkeypatch, handler)
    with pytest.raises(OllamaError, match="did not respond in time"):
        collect()


def test_chat_stream_connection_refused_is_friendly(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused")
    patch_transport(monkeypatch, handler)
    with pytest.raises(OllamaError, match="Cannot reach Ollama"):
        collect()


# ---- pipeline ----------------------------------------------------------------------------

@pytest.fixture
def bot(settings, embedder):
    settings.min_dense_score = 0.0  # the hashing test embedder's cosines are not comparable to a real model's
    return StudyBot(settings, embedder=embedder)


def fake_llm(monkeypatch, text, calls=None):
    async def stream(base_url, model, messages, **kwargs):
        if calls is not None:
            calls.append((model, messages, kwargs))
        for piece in [text[:10], text[10:]]:
            yield ChatChunk(piece)
        yield ChatChunk("", True, eval_count=20, eval_seconds=2.0)
    monkeypatch.setattr(pipeline_module, "chat_stream", stream)


def test_ingest_indexes_skips_unchanged_and_reindexes_changed(bot, tmp_path):
    path = notes_docx(tmp_path / "Notes.docx")
    first = bot.ingest(str(path), "cv")
    assert not first.skipped and first.chunks >= 1
    again = bot.ingest(str(path), "cv")
    assert again.skipped and again.document_id == first.document_id
    forced = bot.ingest(str(path), "cv", force=True)
    assert not forced.skipped and len(bot.store.list_documents()) == 1


def test_ingest_errors_are_ingest_errors(bot, tmp_path):
    with pytest.raises(IngestError):
        bot.ingest(str(tmp_path / "missing.pdf"), "cv")


def test_ask_streams_cites_and_reports_stats(bot, tmp_path, monkeypatch):
    bot.ingest(str(notes_docx(tmp_path / "Notes.docx")), "cv")
    calls, streamed = [], []
    fake_llm(monkeypatch, "Bicubic uses 16 pixels [1] and also [7].", calls)
    answer = asyncio.run(bot.ask("how many pixels does bicubic use", ["cv"], on_token=streamed.append))
    assert answer.cited == [1] and answer.invalid_citations == 1 and "[7]" not in answer.text
    assert "".join(streamed) == "Bicubic uses 16 pixels [1] and also [7]."
    assert not answer.refused and not answer.gated and answer.tokens == 20 and answer.tokens_per_second == 10.0
    model, messages, kwargs = calls[0]
    assert model == bot.settings.llm_model and kwargs["num_ctx"] == bot.settings.num_ctx
    assert "Question: how many pixels does bicubic use" in messages[1]["content"]


def test_ask_uses_requested_model(bot, tmp_path, monkeypatch):
    bot.ingest(str(notes_docx(tmp_path / "Notes.docx")), "cv")
    calls = []
    fake_llm(monkeypatch, "ok [1]", calls)
    asyncio.run(bot.ask("interpolation", ["cv"], model="other:1b"))
    assert calls[0][0] == "other:1b"


def test_gate_refuses_without_calling_the_llm(bot, tmp_path, monkeypatch):
    bot.ingest(str(notes_docx(tmp_path / "Notes.docx")), "cv")
    calls = []
    fake_llm(monkeypatch, "should not be used", calls)
    bot.settings.min_dense_score = 0.99
    answer = asyncio.run(bot.ask("interpolation", ["cv"]))
    assert answer.gated and answer.refused and answer.text == prompt.REFUSAL and calls == []
    ungated = asyncio.run(bot.ask("interpolation", ["cv"], use_gate=False))
    assert not ungated.gated and len(calls) == 1


def test_ask_with_empty_index_refuses(bot, monkeypatch):
    calls = []
    fake_llm(monkeypatch, "x", calls)
    answer = asyncio.run(bot.ask("anything"))
    assert answer.refused and answer.gated and calls == []


def test_model_refusal_is_detected(bot, tmp_path, monkeypatch):
    bot.ingest(str(notes_docx(tmp_path / "Notes.docx")), "cv")
    fake_llm(monkeypatch, prompt.REFUSAL)
    answer = asyncio.run(bot.ask("interpolation", ["cv"]))
    assert answer.refused and not answer.gated


def test_unknown_collection_is_a_keyerror(bot):
    with pytest.raises(KeyError):
        asyncio.run(bot.ask("q", ["nope"]))
