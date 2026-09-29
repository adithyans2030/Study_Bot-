"""Hybrid retrieval: dense (semantic) + BM25 (exact terms), merged with reciprocal rank fusion."""
from dataclasses import dataclass
from typing import Literal, Sequence

from app.rag.embed import EmbedderLike
from app.rag.rerank import RerankerLike
from app.rag.store import ChunkRecord, Store

Mode = Literal["dense", "bm25", "hybrid"]
RRF_K = 60


@dataclass(frozen=True)
class Hit:
    chunk: ChunkRecord
    score: float  # ranking score (RRF, or reranker score when reranking)
    dense: float  # cosine similarity between the query and this chunk


@dataclass(frozen=True)
class Retrieval:
    hits: list[Hit]
    best_dense: float  # cosine of the single closest chunk: the "is this in my materials?" signal


class Retriever:
    def __init__(self, store: Store, embedder: EmbedderLike, reranker: RerankerLike | None = None,
                 candidates: int = 30):
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.candidates = candidates

    def search(self, query: str, collection_ids: Sequence[int] | None = None, k: int = 6,
               mode: Mode = "hybrid", rerank: bool | None = None) -> Retrieval:
        n = max(self.candidates, k)
        qvec = self.embedder.embed_query(query)
        dense = self.store.dense_search(qvec, collection_ids, n)
        best_dense = dense[0][1] if dense else 0.0

        rankings: list[list[int]] = []
        if mode in ("dense", "hybrid"):
            rankings.append([cid for cid, _ in dense])
        if mode in ("bm25", "hybrid"):
            rankings.append([cid for cid, _ in self.store.bm25_search(query, collection_ids, n)])

        fused: dict[int, float] = {}
        for ranking in rankings:
            for rank, cid in enumerate(ranking, start=1):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        ordered = sorted(fused, key=fused.__getitem__, reverse=True)[:n]
        chunks = self.store.get_chunks(ordered)
        ordered = [cid for cid in ordered if cid in chunks]

        use_rerank = self.reranker is not None if rerank is None else rerank
        if use_rerank and self.reranker is None:
            raise ValueError("rerank was requested but no reranker is configured (set STUDYBOT_USE_RERANKER=true)")
        scores = {cid: fused[cid] for cid in ordered}
        if use_rerank and ordered:
            texts = [chunks[cid].header + "\n" + chunks[cid].text for cid in ordered]
            scores = dict(zip(ordered, self.reranker.score(query, texts)))
            ordered = sorted(ordered, key=scores.__getitem__, reverse=True)

        top = ordered[:k]
        cosines = self.store.cosine(top, qvec)
        hits = [Hit(chunks[cid], scores[cid], cosines.get(cid, 0.0)) for cid in top]
        return Retrieval(hits, best_dense)
