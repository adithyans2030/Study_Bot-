"""Turning a follow-up ("and what about its limitations?") into something search can use.

Retrieval only sees the words it is given, so "its limitations" alone finds nothing useful. Three
strategies (`Settings.followup_mode`):
  off     search exactly what was typed
  concat  prepend the previous question. Free and instant; the answer model still sees the real
          question plus the recent conversation.
  llm     ask the language model to rewrite the follow-up as a standalone question. More robust for
          odd references, but costs a model call (seconds on a small GPU).
"""
import re
from typing import Sequence

from app.core.ollama import chat_stream

Turn = tuple[str, str]  # (question, answer)

_REFERENCES = re.compile(
    r"\b(it|its|it's|this|that|these|those|they|them|their|theirs|he|she|him|her|his|hers|"
    r"the (?:former|latter|first|second|third|last|other|same|two)|which (?:one|of (?:them|these|those|the two))|"
    r"both|either|neither|above|previous|earlier)\b", re.IGNORECASE)
_STARTERS = re.compile(r"^\s*(and|also|but|so|then|what about|how about|why|how so|more|another|else)\b", re.IGNORECASE)
SHORT = 6  # a question this short rarely stands on its own
REFERENCE_MAX_WORDS = 10  # in a longer question, "its" usually points to something in the same sentence


def looks_like_follow_up(question: str) -> bool:
    """A cheap check for questions that probably depend on the conversation."""
    words = len(question.split())
    return (words <= SHORT or bool(_STARTERS.match(question))
            or (words <= REFERENCE_MAX_WORDS and bool(_REFERENCES.search(question))))


def concat_query(question: str, history: Sequence[Turn]) -> str:
    return f"{history[-1][0].strip()} {question.strip()}" if history else question


REWRITE_SYSTEM = (
    "You rewrite a student's latest question so it can be understood on its own. Use the earlier "
    "conversation only to resolve words like 'it', 'that' or 'the second one'. Do not answer the "
    "question and do not add new topics. Reply with the rewritten question only, on a single line."
)


def rewrite_messages(question: str, history: Sequence[Turn]) -> list[dict]:
    lines = [f"Student: {q}\nAssistant: {a[:300]}" for q, a in history[-2:]]
    user = "Conversation so far:\n" + "\n".join(lines) + f"\n\nLatest question: {question}\n\nRewritten question:"
    return [{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": user}]


def clean_rewrite(text: str, original: str) -> str | None:
    """The model's rewrite if it looks like a single sensible question, else None (unusable)."""
    line = re.sub(r"^(rewritten question|question)\s*:\s*", "", text.strip().splitlines()[0] if text.strip() else "",
                  flags=re.IGNORECASE).strip().strip('"\'`')
    if not line or len(line) > max(300, 4 * len(original)) or len(line.split()) < 2:
        return None
    return line


async def rewrite_with_llm(base_url: str, model: str, question: str, history: Sequence[Turn],
                           num_ctx: int = 4096) -> str | None:
    """The standalone question, or None if the model failed or produced something unusable."""
    try:
        pieces = [c.text async for c in chat_stream(base_url, model, rewrite_messages(question, history),
                                                    num_ctx=num_ctx, temperature=0.0, num_predict=60)]
    except Exception:
        return None
    return clean_rewrite("".join(pieces), question)


async def search_query(mode: str, question: str, history: Sequence[Turn], *, base_url: str = "", model: str = "",
                       num_ctx: int = 4096) -> str:
    """The text to search with, given the conversation so far."""
    if mode == "off" or not history or not looks_like_follow_up(question):
        return question
    if mode == "llm":
        rewritten = await rewrite_with_llm(base_url, model, question, history, num_ctx)
        if rewritten is not None:
            return rewritten
    return concat_query(question, history)  # concat mode, or the model was unavailable/unusable
