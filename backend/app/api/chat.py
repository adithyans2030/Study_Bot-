"""Ask a question and stream the answer with its sources (Server-Sent Events).

Events, in order:
  conversation  {"id", "title"}: which saved chat this belongs to (created on the first question)
  query         {"text"}: only for follow-ups; the standalone question that was actually searched for
  sources       the retrieved passages, before any text
  token         {"text": "..."} zero or more times (raw model output)
  done          the FINAL result; its "text" has invalid citation markers removed and must replace the
                streamed text. Also says whether the answer was refused, uncited or empty.
  error         {"message": "..."} instead of done if something failed

The question is saved as soon as it arrives; the answer is saved when it completes.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.api.jobs import SSE_HEADERS
from app.core.accounts import User
from app.core.ollama import OllamaError
from app.rag import prompt
from app.rag.pipeline import DoneEvent, QueryEvent, SourcesEvent, TokenEvent

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger("studybot.chat")
NO_MATERIALS = "You haven't added any study materials yet. Upload a file or add a YouTube link first."


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    collections: list[str] | None = None  # names; omit to search all of your collections
    conversation_id: int | None = None  # omit to start a new saved chat


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def source_json(number: int, hit) -> dict:
    chunk = hit.chunk
    return {"n": number, "title": chunk.doc_title, "type": chunk.source_type, "location": prompt.location(hit),
            "url": prompt.source_url(hit), "header": chunk.header, "snippet": chunk.text[:400]}


def done_json(answer) -> dict:
    return {"text": answer.text, "cited": answer.cited, "invalid_citations": answer.invalid_citations,
            "refused": answer.refused, "gated": answer.gated, "empty": answer.empty,
            "seconds": round(answer.total_seconds, 1), "first_token_seconds": round(answer.first_token_seconds, 1)}


@router.post("/chat")
async def chat(body: ChatIn, request: Request, user: User = Depends(current_user)) -> StreamingResponse:
    state = request.app.state
    chats = state.conversations
    try:  # validate names now, so an unknown one is a clean 404 instead of a broken stream
        state.store.collection_ids(body.collections, user.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"No collection named {exc}.") from exc

    if body.conversation_id is not None:
        conversation = await asyncio.to_thread(chats.get, body.conversation_id, user.id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        conversation = await asyncio.to_thread(chats.create, user.id, body.question)
    await asyncio.to_thread(chats.add_message, conversation.id, user.id, "user", body.question)
    history = await asyncio.to_thread(chats.recent_turns, conversation.id, user.id, state.settings.history_turns)
    has_materials = bool(await asyncio.to_thread(state.store.list_documents, None, user.id))

    async def save_answer(text: str, sources: list, meta: dict) -> None:
        await asyncio.to_thread(chats.add_message, conversation.id, user.id, "assistant", text, sources, meta)

    async def stream():
        yield _sse("conversation", {"id": conversation.id, "title": conversation.title})
        if not has_materials:
            payload = {"text": NO_MATERIALS, "cited": [], "invalid_citations": 0, "refused": True, "gated": True,
                       "empty": False, "seconds": 0, "first_token_seconds": 0}
            await save_answer(NO_MATERIALS, [], {k: payload[k] for k in ("cited", "refused", "gated", "empty")})
            yield _sse("sources", [])
            yield _sse("done", payload)
            return
        sources: list = []
        search_query = None
        try:
            async for event in state.bot.ask_stream(body.question, body.collections, user_id=user.id, history=history):
                if isinstance(event, QueryEvent):
                    search_query = event.text
                    yield _sse("query", {"text": event.text})
                elif isinstance(event, SourcesEvent):
                    sources = [source_json(i, h) for i, h in enumerate(event.hits, start=1)]
                    yield _sse("sources", sources)
                elif isinstance(event, TokenEvent):
                    yield _sse("token", {"text": event.text})
                elif isinstance(event, DoneEvent):
                    payload = done_json(event.answer)
                    kept = [] if event.answer.refused else sources  # nothing was answered from them
                    meta = {k: payload[k] for k in ("cited", "invalid_citations", "refused", "gated", "empty", "seconds")}
                    if search_query:
                        meta["search_query"] = search_query
                    await save_answer(payload["text"], kept, meta)
                    yield _sse("done", payload)
        except OllamaError as exc:
            yield _sse("error", {"message": str(exc)})
        except Exception:
            log.exception("chat failed")
            yield _sse("error", {"message": "Something went wrong answering that. Please try again."})

    return StreamingResponse(stream(), media_type="text/event-stream", headers=SSE_HEADERS)
