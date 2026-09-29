"""Minimal async Ollama client: model listing and streaming chat."""
import json
from dataclasses import dataclass
from typing import AsyncIterator

import httpx


class OllamaError(Exception):
    """Ollama refused or failed a request. The message is safe to show to the user."""


@dataclass(frozen=True)
class ChatChunk:
    text: str
    done: bool = False
    eval_count: int = 0  # generated tokens (final chunk only)
    eval_seconds: float = 0.0  # generation time (final chunk only)
    prompt_tokens: int = 0  # prompt tokens processed (final chunk only)
    prompt_seconds: float = 0.0  # prompt processing time (final chunk only)


async def chat_stream(base_url: str, model: str, messages: list[dict], *, num_ctx: int = 4096,
                      temperature: float = 0.2, num_predict: int = 700,
                      keep_alive: str = "30m") -> AsyncIterator[ChatChunk]:
    payload = {
        "model": model, "messages": messages, "stream": True, "keep_alive": keep_alive,
        "options": {"num_ctx": num_ctx, "temperature": temperature, "num_predict": num_predict},
    }
    # A busy or memory-starved Ollama can be slow to accept a connection; the first token can also
    # wait on model load / CPU offload.
    timeout = httpx.Timeout(600.0, connect=20.0)
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", "replace")
                    try:
                        body = json.loads(body).get("error", body)
                    except ValueError:
                        pass
                    raise OllamaError(f"Ollama returned {response.status_code}: {body}")
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise OllamaError(data["error"])
                    text = data.get("message", {}).get("content", "")
                    if data.get("done"):
                        yield ChatChunk(text, True, data.get("eval_count", 0), data.get("eval_duration", 0) / 1e9,
                                        data.get("prompt_eval_count", 0), data.get("prompt_eval_duration", 0) / 1e9)
                        return
                    if text:
                        yield ChatChunk(text)
    except httpx.ConnectError as exc:
        raise OllamaError(f"Cannot reach Ollama at {base_url}. Is it running?") from exc
    except httpx.TimeoutException as exc:
        raise OllamaError(f"Ollama at {base_url} did not respond in time. It may be busy or low on memory.") from exc


async def list_models(base_url: str, timeout: float = 2.0) -> list[str]:
    """Return the names of models pulled into the local Ollama, e.g. ['llama3.2:3b']."""
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        response = await client.get("/api/tags")
        response.raise_for_status()
        return [model["name"] for model in response.json().get("models", [])]


def normalize_model_name(name: str) -> str:
    """Ollama treats a bare 'llama3.2' as 'llama3.2:latest'."""
    return name if ":" in name else f"{name}:latest"
