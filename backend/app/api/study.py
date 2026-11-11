"""Study features for StudyBot: summaries, quiz generation, flashcards, and exam-driven plans."""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import current_user
from app.core.accounts import User
from app.core.ollama import chat_stream, OllamaError
from app.okf.models import OKFNode
from app.study.planner import PlannedDay, build_plan

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


class SourceRef(BaseModel):
    """Which numbered knowledge node a generated question/card was actually grounded in -
    the same 'cite back to something real' contract chat answers already honour."""
    n: int
    node_id: int
    title: str
    type: str
    source_document: str


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    source: Optional[SourceRef] = None


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
    source: Optional[SourceRef] = None


class FlashcardsResponse(BaseModel):
    cards: list[Flashcard]


class QuizAttemptItem(BaseModel):
    node_id: Optional[int] = None  # None when the question's source didn't resolve
    correct: bool


class QuizAttemptsRequest(BaseModel):
    attempts: list[QuizAttemptItem]


class QuizAttemptsResponse(BaseModel):
    recorded: int


class PlanNode(BaseModel):
    node_id: int
    title: str
    type: str
    source_document: str
    status: Literal["untested", "weak", "known"]
    accuracy: Optional[float] = None
    last_attempt_at: Optional[float] = None


class PlanDay(BaseModel):
    date: str
    day_index: int
    nodes: list[PlanNode]


class StudyPlanResponse(BaseModel):
    deadline: str
    days_remaining: int
    days: list[PlanDay]


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


CONTEXT_BUDGET_CHARS = 8000


def _get_context(request: Request, collection_id: int, user_id: int,
                 document_id: Optional[int] = None) -> tuple[str, list[OKFNode]]:
    """Retrieve numbered textual context from OKF nodes, for grounding generated questions/cards
    back to a real node (mirrors app/rag/prompt.py's `[n] label\\ntext` citation convention).

    The character budget is enforced here, per whole node, rather than by the caller slicing the
    joined string afterward: slicing after numbering would let a node that got cut off keep a
    "valid" index, so a model citing it would look grounded in content it never actually saw."""
    okf_store = getattr(request.app.state, "okf_store", None)
    if not okf_store:
        return "", []

    nodes = okf_store.list_nodes(collection_id=collection_id, user_id=user_id, limit=35)
    if document_id:
        nodes = [n for n in nodes if n.document_id == document_id]

    if not nodes:
        return "", []

    included: list[OKFNode] = []
    blocks: list[str] = []
    length = 0
    for i, node in enumerate(nodes, 1):
        block = f"[{i}] {node.title} ({node.type})\n{node.body}"
        added = len(block) + (len("\n\n---\n\n") if blocks else 0)
        if blocks and length + added > CONTEXT_BUDGET_CHARS:
            break
        blocks.append(block)
        included.append(node)
        length += added

    return "\n\n---\n\n".join(blocks), included


def _resolve_source(raw: object, nodes: list[OKFNode]) -> Optional[SourceRef]:
    """Validate an LLM-supplied node index against the nodes actually shown in the prompt - never
    trust it blindly (same discipline as app/rag/prompt.py's extract_citations). Any bad shape
    (missing, non-numeric, out of range, zero/negative) degrades to None rather than raising."""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if not (1 <= n <= len(nodes)):
        return None
    node = nodes[n - 1]
    return SourceRef(n=n, node_id=node.node_id, title=node.title, type=node.type,
                     source_document=node.source_document)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/summarize", response_model=SummaryResponse)
async def summarize(
    collection_id: int,
    req: SummaryRequest,
    request: Request,
    user: User = Depends(current_user),
) -> SummaryResponse:
    """Generate a structured summary of notes in this collection."""
    context, _nodes = _get_context(request, collection_id, user.id, req.document_id)
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
{context}

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
    context, nodes = _get_context(request, collection_id, user.id, req.document_id)
    if not context:
        raise HTTPException(
            status_code=422,
            detail="No knowledge nodes found for this collection. Upload materials first."
        )

    topic_str = f" on the topic of '{req.topic}'" if req.topic else ""
    system = "You are an academic exam writer. Create fair, precise multiple-choice questions testing comprehension."
    prompt = f"""Create {req.num_questions} {req.difficulty}-difficulty multiple-choice questions{topic_str} based on these study notes.

Notes:
{context}

Every question must be grounded in exactly one numbered note above; set "source" to its number.

Return a JSON array of objects with these exact keys:
[
  {{
    "question": "<question text>",
    "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
    "correct_index": 0,
    "explanation": "<why this option is correct and others are not>",
    "source": 1
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
                    source=_resolve_source(item.get("source"), nodes),
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
    context, nodes = _get_context(request, collection_id, user.id, req.document_id)
    if not context:
        raise HTTPException(
            status_code=422,
            detail="No knowledge nodes found for this collection. Upload materials first."
        )

    topic_str = f" focusing on '{req.topic}'" if req.topic else ""
    system = "You are a flashcard generator. Create concise, high-yield flashcards for active recall."
    prompt = f"""Create {req.num_cards} flashcards{topic_str} based on these study notes.

Notes:
{context}

Every flashcard must be grounded in exactly one numbered note above; set "source" to its number.

Return a JSON array of objects:
[
  {{
    "front": "<question, term, or prompt>",
    "back": "<concise explanation, definition, or answer>",
    "tags": ["<tag1>", "<tag2>"],
    "source": 1
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
                    source=_resolve_source(item.get("source"), nodes),
                ))
        except (ValueError, TypeError):
            continue

    if not cards:
        raise HTTPException(status_code=500, detail="Failed to extract valid flashcards from model response.")

    return FlashcardsResponse(cards=cards)


def _plan_day_json(day: PlannedDay) -> PlanDay:
    return PlanDay(date=day.date.isoformat(), day_index=day.day_index, nodes=[
        PlanNode(node_id=n.node_id, title=n.title, type=n.type, source_document=n.source_document,
                status=n.status, accuracy=n.accuracy, last_attempt_at=n.last_attempt_at)
        for n in day.nodes
    ])


@router.post("/quiz/attempts", response_model=QuizAttemptsResponse)
def record_quiz_attempts(
    collection_id: int,
    req: QuizAttemptsRequest,
    request: Request,
    user: User = Depends(current_user),
) -> QuizAttemptsResponse:
    """Record a submitted quiz's results, so the study plan below can tell weak/untested topics
    from mastered ones. node_id is None for questions whose source never resolved - stored, but
    excluded from ranking (see AttemptsStore.node_stats)."""
    attempts_store = getattr(request.app.state, "attempts_store", None)
    if not attempts_store:
        return QuizAttemptsResponse(recorded=0)
    recorded = attempts_store.record_attempts(
        user.id, collection_id, [(a.node_id, a.correct) for a in req.attempts]
    )
    return QuizAttemptsResponse(recorded=recorded)


@router.get("/plan", response_model=StudyPlanResponse)
def generate_plan(
    collection_id: int,
    deadline: date,
    request: Request,
    user: User = Depends(current_user),
) -> StudyPlanResponse:
    """Build a day-by-day review schedule toward `deadline`, surfacing untested and weak topics
    first. A pure derived read over stored nodes + attempt aggregates, no LLM call - hence GET,
    unlike the three endpoints above."""
    today = date.today()
    if deadline < today:
        raise HTTPException(status_code=422, detail="Deadline must be today or later.")

    okf_store = getattr(request.app.state, "okf_store", None)
    nodes = okf_store.list_nodes(collection_id=collection_id, user_id=user.id, limit=10000) if okf_store else []
    if not nodes:
        raise HTTPException(
            status_code=422,
            detail="No knowledge nodes found for this collection. Upload materials first."
        )

    attempts_store = getattr(request.app.state, "attempts_store", None)
    stats = attempts_store.node_stats(collection_id, user.id) if attempts_store else {}

    plan = build_plan(nodes, stats, today, deadline)
    return StudyPlanResponse(
        deadline=plan.deadline.isoformat(),
        days_remaining=plan.days_remaining,
        days=[_plan_day_json(d) for d in plan.days],
    )
