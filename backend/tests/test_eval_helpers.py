"""Tests for the evaluation tooling itself: a wrong measuring stick is worse than none."""
import collections

from app.rag.store import ChunkRecord
from eval.common import is_relevant, keywords_ok, load_golden
from eval.run_retrieval import group_of, summarize


def chunk(source="C:/x/Computer_Vision_Unit_2_Quick_Revision.pdf", **meta):
    return ChunkRecord(1, 1, "t", "pdf", source, 0, "h", "text", meta)


def test_is_relevant_matches_document_and_page_range():
    expect = [{"doc": "Unit_2", "pages": [3, 4]}]
    assert is_relevant(chunk(page_start=3, page_end=3), expect)
    assert is_relevant(chunk(page_start=2, page_end=4), expect), "a chunk spanning pages counts if it covers one"
    assert not is_relevant(chunk(page_start=1, page_end=2), expect)
    assert not is_relevant(chunk("C:/x/Unit_1.pdf", page_start=3, page_end=3), expect), "wrong document"
    assert not is_relevant(chunk(), expect), "no page info can never match a page expectation"


def test_is_relevant_matches_time_windows_by_overlap():
    expect = [{"doc": "tVskbekONlw", "t": [100, 200]}]
    src = "https://www.youtube.com/watch?v=tVskbekONlw"
    assert is_relevant(chunk(src, t_start=150, t_end=240), expect)
    assert is_relevant(chunk(src, t_start=50, t_end=110), expect)
    assert not is_relevant(chunk(src, t_start=200, t_end=290), expect), "touching the edge is not overlap"
    assert not is_relevant(chunk(src, t_start=0, t_end=100), expect)
    assert not is_relevant(chunk("other", t_start=150, t_end=180), expect)


def test_keywords_ok_requires_every_entry_and_any_alternative():
    assert keywords_ok("Sobel is FIRST-order and directional", ["first-order|first order", "directional"])
    assert not keywords_ok("Sobel is first order", ["first order", "second order"])
    assert keywords_ok("anything", [])


def test_group_of_and_summarize():
    assert group_of("cv-03") == "notes-formal" and group_of("cv-56") == "notes-casual" and group_of("yt-02") == "video"
    summary = summarize([1, 2, None, 5])
    assert summary["n"] == 4 and summary["hit@1"] == 0.25 and summary["hit@3"] == 0.5 and summary["hit@5"] == 0.75
    assert abs(summary["mrr"] - (1 + 0.5 + 0 + 0.2) / 4) < 1e-9


def test_golden_set_is_well_formed():
    golden = load_golden()
    ids = [g["id"] for g in golden]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    assert len(golden) >= 60
    unanswerable = [g for g in golden if not g["answerable"]]
    assert len(unanswerable) / len(golden) >= 0.15
    for item in golden:
        assert item["q"].strip().endswith(("?", ".")) or item["id"].startswith("cv-5"), item["id"]
        assert item["collection"] in ("computer-vision", "mlops")
        if item["answerable"]:
            assert item["expect"] and item["kw"], f"{item['id']} needs expected location and keywords"
            for target in item["expect"]:
                assert ("pages" in target) != ("t" in target)
                if "t" in target:
                    assert target["t"][0] < target["t"][1]
        else:
            assert item["expect"] == [], item["id"]
    per_collection = collections.Counter(g["collection"] for g in golden)
    assert per_collection["mlops"] >= 8
