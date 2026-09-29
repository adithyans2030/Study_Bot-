import numpy as np
import pytest

from app.ingest.chunker import chunk_document
from app.ingest.types import Chunk, LoadedDocument, Segment
from app.rag.retrieve import Retriever
from app.rag.store import Store, fts_query


def make_doc(source, texts, title="Doc", source_type="pdf"):
    segments = [Segment(t, (f"Section {i}",), page=i + 1) for i, t in enumerate(texts)]
    return LoadedDocument(title, source_type, source, "hash-" + source, segments)


def index(store, embedder, collection, doc):
    cid = store.get_or_create_collection(collection)
    chunks = chunk_document(doc)
    return store.add_document(cid, doc, chunks, embedder.embed_passages([c.header + "\n" + c.text for c in chunks]))


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


# ---- FTS query building ------------------------------------------------------------------

def test_fts_query_drops_stopwords_and_quotes_terms():
    assert fts_query("What is the difference between Sobel and Laplacian?") == '"sobel" OR "laplacian"'


def test_fts_query_survives_fts_syntax_characters():
    q = fts_query('AND OR NOT "quoted" (paren) * near/2 c++ -minus')
    assert q is not None and '"' in q and "(" not in q and "*" not in q


def test_fts_query_none_when_only_stopwords():
    assert fts_query("what is the") is None


# ---- store -------------------------------------------------------------------------------

def test_dense_and_bm25_find_the_matching_chunk(store, embedder):
    index(store, embedder, "cv", make_doc("a", ["Sobel is a first order gradient operator " * 5,
                                                 "Otsu picks a threshold from the histogram " * 5]))
    cid = store.collection_ids(["cv"])
    dense = store.dense_search(embedder.embed_query("sobel gradient operator"), cid, 5)
    bm25 = store.bm25_search("sobel gradient operator", cid, 5)
    top_dense = store.get_chunks([dense[0][0]])[dense[0][0]]
    top_bm25 = store.get_chunks([bm25[0][0]])[bm25[0][0]]
    assert "Sobel" in top_dense.text and "Sobel" in top_bm25.text
    assert dense[0][1] > dense[1][1]


def test_search_is_scoped_to_collections(store, embedder):
    index(store, embedder, "cv", make_doc("a", ["histogram equalization improves contrast " * 5]))
    index(store, embedder, "mlops", make_doc("b", ["mlflow tracking logs experiment metrics " * 5]))
    cv, mlops = store.collection_ids(["cv"]), store.collection_ids(["mlops"])
    q = embedder.embed_query("mlflow tracking metrics")
    assert "mlflow" in store.get_chunks([store.dense_search(q, mlops, 1)[0][0]]).popitem()[1].text
    assert all("mlflow" not in c.text for c in store.get_chunks([i for i, _ in store.dense_search(q, cv, 5)]).values())
    assert store.bm25_search("mlflow", cv, 5) == []
    assert len(store.bm25_search("mlflow", None, 5)) == 1


def test_unknown_collection_raises_keyerror(store):
    with pytest.raises(KeyError):
        store.collection_ids(["missing"])


def test_reingest_same_source_replaces_atomically(store, embedder):
    index(store, embedder, "cv", make_doc("a", ["old content about sobel " * 10]))
    index(store, embedder, "cv", make_doc("a", ["new content about laplacian " * 10]))
    cid = store.collection_ids(["cv"])
    assert len(store.list_documents()) == 1
    assert store.bm25_search("sobel", cid, 5) == []
    assert len(store.bm25_search("laplacian", cid, 5)) == 1
    dense = store.dense_search(embedder.embed_query("laplacian"), cid, 10)
    assert len(dense) == 1, "old vectors must be gone too"


def test_failed_replace_rolls_back_and_keeps_the_old_version(store, embedder):
    index(store, embedder, "cv", make_doc("a", ["original content about sobel " * 10]))
    cid = store.get_or_create_collection("cv")
    bad_doc = make_doc("a", ["replacement"])
    bad_chunks = [Chunk(0, "h", "replacement text", {"bad": object()})]  # not JSON serialisable
    with pytest.raises(TypeError):
        store.add_document(cid, bad_doc, bad_chunks, embedder.embed_passages(["replacement text"]))
    assert len(store.bm25_search("sobel", [cid], 5)) == 1
    assert len(store.dense_search(embedder.embed_query("sobel"), [cid], 5)) == 1


def test_delete_document_removes_it_from_every_index(store, embedder):
    doc_id = index(store, embedder, "cv", make_doc("a", ["sobel operator notes " * 10]))
    cid = store.collection_ids(["cv"])
    assert store.delete_document(doc_id) is True
    assert store.bm25_search("sobel", cid, 5) == []
    assert store.dense_search(embedder.embed_query("sobel"), cid, 5) == []
    assert store.delete_document(doc_id) is False


def test_dense_cache_is_invalidated_by_writes(store, embedder):
    cid = store.get_or_create_collection("cv")
    q = embedder.embed_query("sobel")
    assert store.dense_search(q, [cid], 5) == []
    index(store, embedder, "cv", make_doc("a", ["sobel operator " * 10]))
    assert len(store.dense_search(q, [cid], 5)) == 1


def test_list_collections_counts(store, embedder):
    index(store, embedder, "cv", make_doc("a", ["one " * 30, "two " * 30]))
    (row,) = store.list_collections()
    assert row["name"] == "cv" and row["documents"] == 1 and row["chunks"] >= 1


def test_add_document_length_mismatch(store, embedder):
    cid = store.get_or_create_collection("cv")
    with pytest.raises(ValueError):
        store.add_document(cid, make_doc("a", ["x"]), [Chunk(0, "h", "t", {})], np.zeros((2, 4), dtype=np.float32))


# ---- retriever ---------------------------------------------------------------------------

class PreferHistogram:
    def score(self, query, texts):
        return [1.0 if "Histogram" in text else 0.0 for text in texts]


def build(store, embedder):
    index(store, embedder, "cv", make_doc("a", [
        "Sobel first order derivative directional gradient edge detection " * 4,
        "Laplacian second order derivative noise sensitive edge detection " * 4,
        "Histogram equalization redistributes intensity values for contrast " * 4,
    ]))
    return Retriever(store, embedder, candidates=10)


def test_hybrid_returns_relevant_first_with_scores(store, embedder):
    retriever = build(store, embedder)
    result = retriever.search("first order derivative sobel", store.collection_ids(["cv"]), k=2)
    assert "Sobel" in result.hits[0].chunk.text
    assert result.best_dense == pytest.approx(max(h.dense for h in retriever.search(
        "first order derivative sobel", None, k=3, mode="dense").hits))
    assert all(h.dense >= 0 for h in result.hits)


def test_modes_are_independent(store, embedder):
    retriever = build(store, embedder)
    for mode in ("dense", "bm25", "hybrid"):
        hits = retriever.search("laplacian noise", None, k=1, mode=mode).hits
        assert "Laplacian" in hits[0].chunk.text, mode


def test_bm25_mode_with_only_stopwords_returns_nothing(store, embedder):
    assert build(store, embedder).search("what is the", None, mode="bm25").hits == []


def test_reranker_can_reorder_and_is_optional(store, embedder):
    retriever = build(store, embedder)
    query = "sobel first order derivative"
    assert "Sobel" in retriever.search(query, None, k=3).hits[0].chunk.text

    retriever.reranker = PreferHistogram()
    assert "Histogram" in retriever.search(query, None, k=3, rerank=True).hits[0].chunk.text
    assert "Sobel" in retriever.search(query, None, k=3, rerank=False).hits[0].chunk.text
    assert "Histogram" in retriever.search(query, None, k=3).hits[0].chunk.text, "a configured reranker is on by default"


def test_requesting_rerank_without_a_reranker_fails_loudly(store, embedder):
    retriever = build(store, embedder)
    with pytest.raises(ValueError, match="no reranker"):
        retriever.search("sobel", None, rerank=True)


def test_empty_store_returns_no_hits(store, embedder):
    result = Retriever(store, embedder).search("anything", None)
    assert result.hits == [] and result.best_dense == 0.0
