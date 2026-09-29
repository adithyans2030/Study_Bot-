"""Optional cross-encoder reranker (fastembed, CPU). Kept only if the eval shows it helps."""
from pathlib import Path
from typing import Protocol, Sequence


class RerankerLike(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class Reranker:
    def __init__(self, model_name: str, cache_dir: Path):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self._model = None

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = TextCrossEncoder(self.model_name, cache_dir=str(self.cache_dir))
        return [float(s) for s in self._model.rerank(query, list(texts))]
