import re

from app.ingest.chunker import ChunkingConfig, approx_tokens, chunk_document
from app.ingest.types import LoadedDocument, Segment


def doc_of(segments, source_type="pdf", title="Notes"):
    return LoadedDocument(title=title, source_type=source_type, source="x", content_hash="h", segments=segments)


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def test_each_section_becomes_a_chunk_with_heading_header():
    segments = [Segment("Alpha " * 100, ("A",), page=1), Segment("Beta " * 100, ("B",), page=2)]
    chunks = chunk_document(doc_of(segments))
    assert [c.header for c in chunks] == ["Notes › A", "Notes › B"]
    assert chunks[0].meta["page_start"] == 1 and chunks[1].meta["page_start"] == 2
    assert [c.ordinal for c in chunks] == [0, 1]


def test_tiny_sibling_sections_merge_and_keep_their_subheadings():
    segments = [
        Segment("Replaces a pixel with the minimum.", ("5. Filtering", "Minimum Filter"), page=2),
        Segment("Replaces a pixel with the maximum.", ("5. Filtering", "Maximum Filter"), page=2),
    ]
    chunks = chunk_document(doc_of(segments))
    assert len(chunks) == 1
    assert chunks[0].header == "Notes › 5. Filtering"
    assert "Minimum Filter" in chunks[0].text and "Maximum Filter" in chunks[0].text


def test_tiny_sections_do_not_merge_across_different_top_level_headings():
    segments = [Segment("short one", ("A", "x"), page=1), Segment("short two", ("B", "y"), page=1)]
    assert len(chunk_document(doc_of(segments))) == 2


def test_long_section_is_split_with_overlap_and_respects_max():
    sentences = [f"Sentence number {i} explains an important point about images." for i in range(120)]
    cfg = ChunkingConfig(target_tokens=100, max_tokens=140, min_tokens=20, overlap_tokens=30)
    chunks = chunk_document(doc_of([Segment(" ".join(sentences), ("Topic",), page=1)]), cfg)
    assert len(chunks) > 3
    assert all(approx_tokens(c.text) <= cfg.max_tokens + cfg.overlap_tokens for c in chunks)
    # consecutive chunks share text (overlap) so an answer spanning a boundary is still retrievable
    shared = [set(sentences_in(a.text)) & set(sentences_in(b.text)) for a, b in zip(chunks, chunks[1:])]
    assert all(shared)


def sentences_in(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s]


def test_every_word_of_the_input_appears_in_some_chunk():
    segments = [
        Segment("Intro paragraph about vision. " * 30, ("1. Intro",), page=1),
        Segment("- bullet one\n- bullet two", ("1. Intro",), page=1),
        Segment("Table columns: A | B\n- A: x; B: y", ("2. Table",), page=2),
        Segment("A very long unbroken " + "word " * 900, ("3. Long",), page=3),
    ]
    chunks = chunk_document(doc_of(segments), ChunkingConfig(target_tokens=120, max_tokens=160, min_tokens=30, overlap_tokens=20))
    covered = set(words(" ".join(c.text for c in chunks)))
    expected = set(words(" ".join(s.text for s in segments)))
    assert expected <= covered


def test_slides_are_one_chunk_each_and_tiny_slides_attach_to_the_next_content():
    segments = [
        Segment("Body of slide one. " * 40, ("Slide 1: Intro",), slide=1),
        Segment("tiny", ("Slide 2: Title only",), slide=2),
        Segment("also tiny", ("Slide 3: Another",), slide=3),
        Segment("Body of slide four. " * 40, ("Slide 4: Detail",), slide=4),
    ]
    chunks = chunk_document(doc_of(segments, source_type="pptx", title="Deck"))
    assert [c.meta["slides"] for c in chunks] == [[1], [2, 3, 4]]
    assert chunks[0].header == "Deck › Slide 1: Intro"
    assert "Slide 2: Title only" in chunks[1].text, "each merged slide keeps its own title line"


def test_substantial_slides_are_never_merged():
    segments = [Segment("Word " * 80, (f"Slide {n}: T{n}",), slide=n) for n in (1, 2, 3)]
    chunks = chunk_document(doc_of(segments, source_type="pptx"))
    assert [c.meta["slides"] for c in chunks] == [[1], [2], [3]]


def test_page_range_is_recorded_for_sections_spanning_pages():
    segments = [Segment("Para one. " * 30, ("A",), page=3), Segment("Para two. " * 30, ("A",), page=4)]
    (chunk,) = chunk_document(doc_of(segments))
    assert (chunk.meta["page_start"], chunk.meta["page_end"]) == (3, 4)


def transcript(n, step=3.0, words_per=8):
    return [Segment(" ".join(f"w{i}x{j}" for j in range(words_per)), t_start=i * step, t_end=(i + 1) * step)
            for i in range(n)]


def test_transcript_windows_have_times_overlap_and_full_coverage():
    segs = transcript(200)  # 10 minutes of captions
    chunks = chunk_document(doc_of(segs, source_type="youtube", title="Lecture"))
    assert len(chunks) > 5
    assert chunks[0].meta["t_start"] == 0.0 and chunks[-1].meta["t_end"] == segs[-1].t_end
    assert all(b.meta["t_start"] < a.meta["t_end"] for a, b in zip(chunks, chunks[1:])), "windows must overlap"
    assert all(b.meta["t_start"] > a.meta["t_start"] for a, b in zip(chunks, chunks[1:])), "and always advance"
    covered = set(" ".join(c.text for c in chunks).split())
    assert {w for s in segs for w in s.text.split()} <= covered
    assert all(c.header == "Lecture" for c in chunks)


def test_transcript_window_respects_duration_and_token_budget():
    cfg = ChunkingConfig(target_tokens=10_000, window_seconds=30)
    chunks = chunk_document(doc_of(transcript(60), source_type="youtube"), cfg)
    assert all(c.meta["t_end"] - c.meta["t_start"] <= 30 + 3 for c in chunks)


def test_single_short_transcript_is_one_chunk():
    chunks = chunk_document(doc_of(transcript(3), source_type="youtube"))
    assert len(chunks) == 1


def test_empty_document_yields_no_chunks():
    assert chunk_document(doc_of([])) == []
