"""Study features for StudyBot: summaries, quiz generation, and flashcards."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import current_user
from app.core.accounts import User
from app.core.ollama import chat_stream, OllamaError

log = logging.getLogger("studybot.api.study")

router = APIRouter(prefix="/api/collections/{collection_id}/study", tags=["study"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SummaryRequest(BaseModel):
    document_id: Optional[int] = None
    focus: Optional[str] = None
    length: str = "medium"  # short | medium | long


class SummaryResponse(BaseModel):
    summary: str
    key_points: list[str]


class QuizRequest(BaseModel):
    document_id: Optional[int] = None
    topic: Optional[str] = None
    num_questions: int = 5
    difficulty: str = "medium"  # easy | medium | hard


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class QuizResponse(BaseModel):
    questions: list[QuizQuestion]


class FlashcardRequest(BaseModel):
    document_id: Optional[int] = None
    topic: Optional[str] = None
    num_cards: int = 10


class Flashcard(BaseModel):
    front: str
    back: str
    tags: list[str] = []


class FlashcardsResponse(BaseModel):
    cards: list[Flashcard]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> any:
    """Extract JSON object or array from LLM response text."""
    text = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
    start = -1
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            start = i
            break
    if start == -1:
        return None
    try:
        return json.loads(text[start:])
    except Exception:
        # Try trimming trailing commas or extra text
        last_brace = max(text.rfind("}"), text.rfind("]"))
        if last_brace > start:
            try:
                return json.loads(text[start:last_brace + 1])
            except Exception:
                return None
        return None


async def _call_llm(request: Request, system: str, prompt: str) -> str:
    """Call Ollama chat endpoint."""
    settings = request.app.state.settings
    ollama_url = settings.ollama_url
    model = settings.llm_model

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    full = ""
    try:
        async for chunk in chat_stream(ollama_url, model, messages, num_ctx=4096, temperature=0.2, num_predict=2048):
            full += chunk.text
    except OllamaError as exc:
        log.warning("Ollama call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}")
    except Exception as exc:
        log.exception("Unexpected error calling Ollama: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to communicate with LLM.")
    return full


def _get_context(request: Request, collection_id: int, user_id: int, document_id: Optional[int] = None) -> str:
    """Retrieve textual context from OKF nodes."""
    okf_store = getattr(request.app.state, "okf_store", None)
    if not okf_store:
        return ""

    nodes = okf_store.list_nodes(collection_id=collection_id, user_id=user_id, limit=35)
    if document_id:
        nodes = [n for n in nodes if n.document_id == document_id]

    if not nodes:
        return ""

    parts = [f"## {n.title} ({n.type})\n{n.body}" for n in nodes]
    return "\n\n---\n\n".join(parts)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/summarize", response_model=SummaryResponse)
async def summarize(
    collection_id: int,
    req: SummaryRequest,
    request: Request,
    user: User = Depends(current_user),
) -> SummaryResponse:
    """Generate a structured summary of notes in this collection."""
    context = _get_context(request, collection_id, user.id, req.document_id)
    if not context:
        raise HTTPException(
            status_code=422,
            detail="No knowledge nodes found for this collection. Upload materials first."
        )

    length_map = {
        "short": "2-3 concise paragraphs",
        "medium": "4-5 structured paragraphs",
        "long": "comprehensive detailed summary (6-8 paragraphs)",
    }
    length_desc = length_map.get(req.length, "4-5 paragraphs")
    focus_str = f" Focus specifically on: {req.focus}." if req.focus else ""

    system = "You are an expert study assistant. Generate clear, well-structured summaries from student notes."
    prompt = f"""Based on these study notes{focus_str}, create a {length_desc} summary.

Notes:
{context[:8000]}

Return JSON with this exact schema:
{{
  "summary": "<markdown formatted summary>",
  "key_points": ["<key takeaway 1>", "<key takeaway 2>", "<key takeaway 3>"]
}}
Return ONLY valid JSON."""

    raw = await _call_llm(request, system, prompt)
    parsed = _extract_json(raw)

    if isinstance(parsed, dict) and "summary" in parsed:
        return SummaryResponse(
            summary=parsed.get("summary", raw),
            key_points=parsed.get("key_points", []) if isinstance(parsed.get("key_points"), list) else [],
        )

    return SummaryResponse(summary=raw, key_points=[])


@router.post("/quiz", response_model=QuizResponse)
async def generate_quiz(
    collection_id: int,
    req: QuizRequest,
    request: Request,
    user: User = Depends(current_user),
) -> QuizResponse:
    """Generate multiple-choice quiz questions from collection materials."""
    context = _get_context(request, collection_id, user.id, req.document_id)
    if not context:
        raise HTTPException(
            status_code=422,
            detail="No knowledge nodes found for this collection. Upload materials first."
        )

    topic_str = f" on the topic of '{req.topic}'" if req.topic else ""
    system = "You are an academic exam writer. Create fair, precise multiple-choice questions testing comprehension."
    prompt = f"""Create {req.num_questions} {req.difficulty}-difficulty multiple-choice questions{topic_str} based on these study notes.

Notes:
{context[:8000]}

Return a JSON array of objects with these exact keys:
[
  {{
    "question": "<question text>",
    "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
    "correct_index": 0,
    "explanation": "<why this option is correct and others are not>"
  }}
]
Return ONLY the JSON array."""

    raw = await _call_llm(request, system, prompt)
    parsed = _extract_json(raw)

    if not isinstance(parsed, list):
        raise HTTPException(status_code=500, detail="Could not parse quiz questions from LLM response.")

    questions: list[QuizQuestion] = []
    for item in parsed[:req.num_questions]:
        try:
            if "question" in item and "options" in item and isinstance(item["options"], list) and len(item["options"]) >= 2:
                questions.append(QuizQuestion(
                    question=str(item["question"]),
                    options=[str(opt) for opt in item["options"]],
                    correct_index=int(item.get("correct_index", 0)),
                    explanation=str(item.get("explanation", "")),
                ))
        except (ValueError, TypeError):
            continue

    if not questions:
        raise HTTPException(status_code=500, detail="Failed to extract valid questions from model response.")

    return QuizResponse(questions=questions)


@router.post("/flashcards", response_model=FlashcardsResponse)
async def generate_flashcards(
    collection_id: int,
    req: FlashcardRequest,
    request: Request,
    user: User = Depends(current_user),
) -> FlashcardsResponse:
    """Generate flashcards for active recall practice."""
    context = _get_context(request, collection_id, user.id, req.document_id)
    if not context:
        raise HTTPException(
            status_code=422,
            detail="No knowledge nodes found for this collection. Upload materials first."
        )

    topic_str = f" focusing on '{req.topic}'" if req.topic else ""
    system = "You are a flashcard generator. Create concise, high-yield flashcards for active recall."
    prompt = f"""Create {req.num_cards} flashcards{topic_str} based on these study notes.

Notes:
{context[:8000]}

Return a JSON array of objects:
[
  {{
    "front": "<question, term, or prompt>",
    "back": "<concise explanation, definition, or answer>",
    "tags": ["<tag1>", "<tag2>"]
  }}
]
Return ONLY the JSON array."""

    raw = await _call_llm(request, system, prompt)
    parsed = _extract_json(raw)

    if not isinstance(parsed, list):
        raise HTTPException(status_code=500, detail="Could not parse flashcards from LLM response.")

    cards: list[Flashcard] = []
    for item in parsed[:req.num_cards]:
        try:
            if "front" in item and "back" in item:
                cards.append(Flashcard(
                    front=str(item["front"]),
                    back=str(item["back"]),
                    tags=[str(t) for t in item.get("tags", [])] if isinstance(item.get("tags"), list) else [],
                ))
        except (ValueError, TypeError):
            continue

    if not cards:
        raise HTTPException(status_code=500, detail="Failed to extract valid flashcards from model response.")

    return FlashcardsResponse(cards=cards)
