"""Text embeddings via fastembed (ONNX, CPU). Runs on CPU on purpose: the GPU's 4 GB is for the LLM."""
import threading
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np


class EmbedderLike(Protocol):
    def embed_passages(self, texts: Sequence[str]) -> np.ndarray: ...
    def embed_query(self, query: str) -> np.ndarray: ...


class Embedder:
    # bge models retrieve better when short queries carry this instruction.
    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str, cache_dir: Path):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self._model = None
        # The API embeds questions while a background job embeds documents. The lock is taken per
        # batch, so a question waits for at most one small batch instead of a whole document.
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    self._model = TextEmbedding(self.model_name, cache_dir=str(self.cache_dir))
        return self._model

    def warm(self) -> None:
        """Load the model and run one embedding so the first real request is fast."""
        self.embed_query("warm up")

    @staticmethod
    def _normalize(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return (matrix / np.maximum(norms, 1e-12)).astype(np.float32)

    def embed_passages(self, texts: Sequence[str], batch_size: int = 16) -> np.ndarray:
        model = self._load()
        texts = list(texts)
        parts = []
        for start in range(0, len(texts), batch_size):
            with self._lock:
                parts.append(np.array(list(model.embed(texts[start:start + batch_size], batch_size=batch_size)),
                                      dtype=np.float32))
        return self._normalize(np.vstack(parts)) if parts else np.zeros((0, 0), dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        model = self._load()
        with self._lock:
            vector = np.array(list(model.embed([self.QUERY_PREFIX + query])), dtype=np.float32)
        return self._normalize(vector)[0]
