"""Glue: ingest a source, and answer a question from the indexed materials."""
import asyncio
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Sequence

from app.config import Settings
from app.core.ollama import chat_stream
from app.ingest.chunker import ChunkingConfig, chunk_document
from app.ingest.loader import load_source
from app.ingest.types import IngestError
from app.rag import followup, prompt
from app.rag.embed import Embedder, EmbedderLike
from app.rag.rerank import Reranker, RerankerLike
from app.rag.retrieve import Hit, Mode, Retrieval, Retriever
from app.rag.store import LOCAL_USER, Store


@dataclass
class IngestResult:
    document_id: int | None
    title: str
    source_type: str
    chunks: int
    skipped: bool
    warnings: list[str]
    seconds: float
    source: str = ""  # the source recorded in the index (differs from the input for duplicate content)
    duplicate: bool = False  # identical content was already indexed under another source
    _full_text: str = ""  # full document text for OKF extraction
    _collection_id: int = 0   # collection this was indexed into


@dataclass
class Answer:
    text: str
    refused: bool  # the answer is "not in your materials"
    gated: bool  # refused by the retrieval-score gate, without calling the LLM
    hits: list[Hit]
    cited: list[int] = field(default_factory=list)  # 1-based source numbers the answer cites
    invalid_citations: int = 0
    first_token_seconds: float = 0.0
    total_seconds: float = 0.0
    tokens: int = 0
    tokens_per_second: float = 0.0
    prompt_tokens: int = 0
    prompt_seconds: float = 0.0
    best_dense: float = 0.0
    empty: bool = False  # the model produced no real content (e.g. only citation markers)


@dataclass(frozen=True)
class QueryEvent:
    """A follow-up was rewritten; this is what was actually searched for."""
    text: str


@dataclass(frozen=True)
class SourcesEvent:
    """The passages retrieved for a question, sent before generation starts."""
    hits: list[Hit]


@dataclass(frozen=True)
class TokenEvent:
    text: str


@dataclass(frozen=True)
class DoneEvent:
    """The final result. `answer.text` is the CLEANED text (invalid citation markers removed):
    clients must replace whatever they streamed with it."""
    answer: Answer


class StudyBot:
    def __init__(self, settings: Settings, *, embedder: EmbedderLike | None = None,
                 reranker: RerankerLike | None = None, store: Store | None = None):
        self.settings = settings
        settings.ensure_dirs()
        self.store = store or Store(settings.db_path)
        self.embedder = embedder or Embedder(settings.embed_model, settings.models_dir)
        if reranker is None and settings.use_reranker:
            reranker = Reranker(settings.rerank_model, settings.models_dir)
        self.retriever = Retriever(self.store, self.embedder, reranker, settings.candidates)
        self.chunking = ChunkingConfig(settings.chunk_target_tokens, settings.chunk_max_tokens,
                                       settings.chunk_min_tokens, settings.chunk_overlap_tokens)

    def ingest(self, source: str, collection: str = "default", force: bool = False, *, title: str | None = None,
               user_id: int = LOCAL_USER, progress: Callable[[str], None] | None = None) -> IngestResult:
        """Index a file or YouTube link into one of the user's collections.

        `title` overrides the document title (uploads are stored under random names). `progress`
        is called with a stage name: reading, chunking, embedding, indexing."""
        started = time.perf_counter()
        report = progress or (lambda _stage: None)
        report("reading")
        doc = load_source(source, cache_dir=self.settings.cache_dir)
        if title:
            doc.title = title
        collection_id = self.store.get_or_create_collection(collection, user_id)

        existing = self.store.find_document(collection_id, doc.source)
        if existing and existing.sha256 == doc.content_hash and not force:
            return IngestResult(existing.id, existing.title, doc.source_type, existing.chunk_count, True,
                                doc.warnings, time.perf_counter() - started, existing.source)
        if not force:
            twin = self.store.find_document_by_hash(collection_id, doc.content_hash)
            if twin is not None and twin.source != doc.source:
                return IngestResult(twin.id, twin.title, twin.source_type, twin.chunk_count, True,
                                    doc.warnings, time.perf_counter() - started, twin.source, duplicate=True)

        report("chunking")
        chunks = chunk_document(doc, self.chunking)
        if not chunks:
            raise IngestError(f"No usable text found in '{doc.title}'.")
        report("embedding")
        vectors = self.embedder.embed_passages([c.header + "\n" + c.text for c in chunks])
        report("indexing")
        document_id = self.store.add_document(collection_id, doc, chunks, vectors)
        full_text = " ".join(c.text for c in chunks)
        return IngestResult(document_id, doc.title, doc.source_type, len(chunks), False, doc.warnings,
                            time.perf_counter() - started, doc.source,
                            _full_text=full_text, _collection_id=collection_id)

    def search(self, question: str, collections: Sequence[str] | None = None, k: int | None = None,
               mode: Mode = "hybrid", rerank: bool | None = None, user_id: int = LOCAL_USER) -> Retrieval:
        ids = self.store.collection_ids(collections, user_id)
        return self.retriever.search(question, ids, k or self.settings.retrieve_k, mode, rerank)

    async def ask_stream(self, question: str, collections: Sequence[str] | None = None, *,
                         model: str | None = None, use_gate: bool = True, user_id: int = LOCAL_USER,
                         history: Sequence[followup.Turn] = ()
                         ) -> AsyncIterator[QueryEvent | SourcesEvent | TokenEvent | DoneEvent]:
        """Retrieve, then stream the answer. Yields [QueryEvent], SourcesEvent, TokenEvent..., DoneEvent.

        `history` holds earlier (question, answer) exchanges of this conversation, oldest first; a
        follow-up such as "and its limits?" is searched using them (see app/rag/followup.py).
        Raises KeyError (unknown collection) before yielding anything, and OllamaError if the model
        is unreachable, so callers can report a clean error."""
        started = time.perf_counter()
        history = list(history)[-self.settings.history_turns:]
        query = await followup.search_query(self.settings.followup_mode, question, history,
                                            base_url=self.settings.ollama_url, model=model or self.settings.llm_model,
                                            num_ctx=self.settings.num_ctx)
        if query != question:
            yield QueryEvent(query)
        retrieval = await asyncio.to_thread(self.search, query, collections, None, "hybrid", None, user_id)
        hits = retrieval.hits
        yield SourcesEvent(hits)

        if not hits or (use_gate and retrieval.best_dense < self.settings.min_dense_score):
            yield DoneEvent(Answer(prompt.REFUSAL, True, True, hits, best_dense=retrieval.best_dense,
                                   total_seconds=time.perf_counter() - started))
            return

        pieces: list[str] = []
        first_token = 0.0
        tokens, gen_seconds, prompt_tokens, prompt_seconds = 0, 0.0, 0, 0.0
        async for chunk in chat_stream(self.settings.ollama_url, model or self.settings.llm_model,
                                       prompt.build_messages(question, hits, history[-2:]),
                                       num_ctx=self.settings.num_ctx):
            if chunk.text:
                if not pieces:
                    first_token = time.perf_counter() - started
                pieces.append(chunk.text)
                yield TokenEvent(chunk.text)
            if chunk.done:
                tokens, gen_seconds = chunk.eval_count, chunk.eval_seconds
                prompt_tokens, prompt_seconds = chunk.prompt_tokens, chunk.prompt_seconds

        raw = "".join(pieces).strip()
        text, cited, invalid = prompt.extract_citations(raw, len(hits))
        yield DoneEvent(Answer(text, prompt.is_refusal(raw), False, hits, cited, invalid, first_token,
                               time.perf_counter() - started, tokens, tokens / gen_seconds if gen_seconds else 0.0,
                               prompt_tokens, prompt_seconds, retrieval.best_dense, prompt.is_empty_answer(text)))

    async def ask(self, question: str, collections: Sequence[str] | None = None, *, model: str | None = None,
                  use_gate: bool = True, on_token: Callable[[str], None] | None = None,
                  user_id: int = LOCAL_USER, history: Sequence[followup.Turn] = ()) -> Answer:
        answer: Answer | None = None
        async for event in self.ask_stream(question, collections, model=model, use_gate=use_gate, user_id=user_id,
                                           history=history):
            if isinstance(event, TokenEvent) and on_token:
                on_token(event.text)
            elif isinstance(event, DoneEvent):
                answer = event.answer
        assert answer is not None
        return answer

