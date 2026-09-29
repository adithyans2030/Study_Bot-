"""OKF Generator — sends document text to Ollama and extracts structured knowledge nodes."""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from app.okf.models import OKFNode

log = logging.getLogger("studybot.okf.generator")

SYSTEM_PROMPT = """You are a knowledge extraction engine. Given a piece of study material, extract
structured knowledge nodes in JSON. Each node must have these exact keys:
  type        - one of: concept, definition, procedure, formula, example, summary
  title       - short headline (5-10 words)
  description - one sentence summary
  body        - full explanation in markdown (2-6 sentences)
  tags        - list of 2-5 topic tags
  trust       - always "high"

Return a JSON array of nodes. Extract 3-10 nodes. Focus on the most important ideas.
Return ONLY the JSON array, no other text."""


def _build_prompt(text: str, source_title: str) -> str:
    excerpt = text[:6000]  # keep within num_ctx budget
    return f"Source: {source_title}\n\n---\n{excerpt}\n---\n\nExtract knowledge nodes as a JSON array."


async def generate_nodes(
    ollama_url: str,
    model: str,
    text: str,
    source_title: str,
    num_ctx: int = 4096,
) -> list[OKFNode]:
    """Call Ollama to extract OKF nodes from `text`. Returns [] on any failure."""
    from app.core.ollama import chat_stream, OllamaError

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_prompt(text, source_title)},
    ]

    full_response = ""
    try:
        async for chunk in chat_stream(
            ollama_url, model, messages,
            num_ctx=num_ctx, temperature=0.1, num_predict=2048
        ):
            full_response += chunk.text
    except OllamaError as exc:
        log.warning("OKF generation failed (Ollama error): %s", exc)
        return []
    except Exception:
        log.exception("OKF generation failed unexpectedly")
        return []

    return _parse_nodes(full_response, source_title)


def _parse_nodes(raw: str, source_title: str) -> list[OKFNode]:
    """Parse the LLM JSON response into OKFNode objects."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find the array inside the response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                log.warning("OKF: could not parse JSON from response (len=%d)", len(raw))
                return []
        else:
            log.warning("OKF: no JSON array found in response")
            return []

    if not isinstance(data, list):
        log.warning("OKF: expected JSON array, got %s", type(data).__name__)
        return []

    nodes = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            nodes.append(OKFNode(
                type=str(item.get("type", "concept")).lower(),
                title=str(item.get("title", "Untitled")),
                description=str(item.get("description", "")),
                body=str(item.get("body", "")),
                tags=[str(t) for t in item.get("tags", [])],
                trust=str(item.get("trust", "high")),
                source_document=source_title,
            ))
        except Exception as exc:
            log.debug("OKF: skipping malformed node: %s", exc)

    log.info("OKF: extracted %d nodes from '%s'", len(nodes), source_title)
    return nodes
