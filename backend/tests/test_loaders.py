import json

import pymupdf
import pytest

from app.ingest import youtube_loader
from app.ingest.loader import load_source
from app.ingest.pdf_loader import _is_bullet_marker, load_pdf
from app.ingest.text_utils import clean_text, prettify_stem, render_table
from app.ingest.types import IngestError
from tests.fixtures import make_pdf, notes_docx, notes_pdf, notes_pptx


# ---- text utils -------------------------------------------------------------------------

def test_clean_text_strips_private_use_bullets_and_spaces():
    assert clean_text("\uf0b7  Useful\u00a0for   noise ") == "Useful for noise"


def test_prettify_stem():
    assert prettify_stem("C:/x/Computer_Vision_Unit_1.pdf") == "Computer Vision Unit 1"


def test_render_table_makes_rows_self_describing():
    text = render_table([["Method", "Speed"], ["Nearest", "Fastest"], ["Bicubic", "Slowest"], ["", ""]])
    assert text.splitlines() == [
        "Table columns: Method | Speed",
        "- Method: Nearest; Speed: Fastest",
        "- Method: Bicubic; Speed: Slowest",
    ]


def test_render_table_empty():
    assert render_table([["", ""]]) == ""


# ---- PDF ---------------------------------------------------------------------------------

def test_pdf_recovers_headings_pages_and_drops_footer(tmp_path):
    doc = load_pdf(notes_pdf(tmp_path / "CV_Notes.pdf"))
    assert doc.title == "CV Notes"
    assert doc.source_type == "pdf"
    by_text = {seg.text: seg for seg in doc.segments}
    sobel = next(s for s in doc.segments if s.text.startswith("Sobel is a first-order"))
    assert sobel.heading == ("1. Edge Detection", "Sobel Operator")
    assert sobel.page == 1
    otsu = next(s for s in doc.segments if s.text.startswith("Otsu"))
    assert otsu.heading == ("2. Thresholding",) and otsu.page == 2
    assert not any("Course Notes" in text for text in by_text), "repeated footer must be removed"
    assert not any(seg.text.strip() == "CV Notes" for seg in doc.segments), "title line is not body text"


def test_pdf_text_continues_under_last_heading_on_next_page(tmp_path):
    doc = load_pdf(notes_pdf(tmp_path / "n.pdf"))
    global_seg = next(s for s in doc.segments if s.text.startswith("Global thresholding"))
    assert global_seg.page == 3 and global_seg.heading == ("2. Thresholding",)


def test_pdf_table_stays_in_place_under_its_own_heading_even_when_footer_is_listed_first(tmp_path):
    """Regression: PyMuPDF lists a footer first in reading order; tables used to jump to page top."""
    doc = pymupdf.open()
    page = doc.new_page()

    def box(rect, text, size=10, font="helv"):
        assert page.insert_textbox(pymupdf.Rect(*rect), text, fontsize=size, fontname=font) >= 0, text

    box((72, 760, 400, 780), "Course Notes | Page 1", 8)  # footer written first
    box((72, 40, 540, 80), "Doc", 20, "hebo")
    box((72, 90, 540, 120), "1. Interpolation", 14, "hebo")
    box((72, 125, 540, 170), "Interpolation estimates pixel values.", 10)
    box((72, 185, 540, 215), "Bicubic", 13, "hebo")
    box((72, 220, 540, 260), "Bicubic uses sixteen neighbours.", 10)
    for r, row in enumerate([("Method", "Neighbours"), ("Bilinear", "4"), ("Bicubic", "16")]):
        for c, text in enumerate(row):
            cell = pymupdf.Rect(72 + c * 150, 280 + r * 24, 222 + c * 150, 304 + r * 24)
            page.draw_rect(cell, color=(0, 0, 0), width=0.8)
            box((cell.x0 + 3, cell.y0 + 3, cell.x1 - 3, cell.y1 - 3), text, 9)
    box((72, 380, 540, 410), "2. Other Topic", 14, "hebo")
    box((72, 415, 540, 450), "Unrelated closing text.", 10)
    path = tmp_path / "table.pdf"
    doc.save(path)

    segments = load_pdf(path).segments
    texts = [s.text for s in segments]
    table_index = next(i for i, t in enumerate(texts) if t.startswith("Table columns"))
    assert "- Method: Bicubic; Neighbours: 16" in texts[table_index]
    assert segments[table_index].heading == ("1. Interpolation", "Bicubic")
    assert table_index > next(i for i, t in enumerate(texts) if t.startswith("Bicubic uses sixteen"))
    assert table_index < next(i for i, t in enumerate(texts) if t.startswith("Unrelated closing"))
    assert next(s for s in segments if s.text.startswith("Unrelated")).heading == ("2. Other Topic",)


def test_pdf_file_is_released_after_loading_so_it_can_be_deleted(tmp_path):
    """Regression: on Windows an unclosed PDF cannot be deleted, so removing an upload failed."""
    path = notes_pdf(tmp_path / "n.pdf")
    load_pdf(path)
    path.unlink()  # raises PermissionError on Windows if PyMuPDF still holds the file open
    assert not path.exists()


def test_error_messages_never_contain_file_paths(tmp_path):
    folder = tmp_path / "secret-folder"
    folder.mkdir()
    bad_pdf = folder / "broken.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4\n" + b"garbage " * 200)
    with pytest.raises(IngestError) as err:
        load_pdf(bad_pdf)
    assert "secret-folder" not in str(err.value) and str(tmp_path) not in str(err.value)
    for name in ("bad.docx", "bad.pptx"):
        broken = folder / name
        broken.write_bytes(b"PK\x03\x04 not a real archive")
        with pytest.raises(IngestError) as err:
            load_source(str(broken))
        assert "secret-folder" not in str(err.value), name


def test_pdf_hash_is_deterministic_and_content_sensitive(tmp_path):
    first = notes_pdf(tmp_path / "a.pdf")
    other = make_pdf(tmp_path / "b.pdf", [[("body", "different words entirely", (72, 100, 540, 150))]])
    assert load_pdf(first).content_hash == load_pdf(first).content_hash
    assert load_pdf(first).content_hash != load_pdf(other).content_hash
    assert len(load_pdf(first).content_hash) == 64


def test_pdf_with_blank_page_warns(tmp_path):
    body = [("body", "Some text " * 20, (72, 100, 540, 200))]
    path = make_pdf(tmp_path / "blank.pdf", [body, [], body])
    doc = load_pdf(path)
    assert any("Page 2" in w for w in doc.warnings)


def test_pdf_with_no_text_is_rejected(tmp_path):
    path = make_pdf(tmp_path / "empty.pdf", [[], []])
    with pytest.raises(IngestError, match="No extractable text"):
        load_pdf(path)


def test_pdf_corrupt_file_is_a_friendly_error(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    with pytest.raises(IngestError, match="Could not open PDF"):
        load_pdf(bad)


def test_pdf_password_protected_is_rejected(tmp_path):
    src = notes_pdf(tmp_path / "plain.pdf")
    locked = tmp_path / "locked.pdf"
    doc = pymupdf.open(src)
    doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    with pytest.raises(IngestError, match="password"):
        load_pdf(locked)


def test_bullet_marker_detection():
    assert _is_bullet_marker("\uf0b7")
    assert _is_bullet_marker(" • ")
    assert not _is_bullet_marker("• text")
    assert not _is_bullet_marker("")


# ---- DOCX / PPTX -------------------------------------------------------------------------

def test_docx_headings_bullets_and_tables(tmp_path):
    doc = load_source(str(notes_docx(tmp_path / "Unit_Notes.docx")))
    assert doc.source_type == "docx" and doc.title == "Unit Notes"
    intro = next(s for s in doc.segments if s.text.startswith("Interpolation estimates"))
    assert intro.heading == ("Interpolation",)
    bullet = next(s for s in doc.segments if "four nearest" in s.text)
    assert bullet.heading == ("Interpolation", "Bilinear") and bullet.text.startswith("- ")
    table = next(s for s in doc.segments if s.text.startswith("Table columns"))
    assert "- Method: Bicubic; Neighbours: 16" in table.text


def test_pptx_one_segment_per_slide_with_notes(tmp_path):
    doc = load_source(str(notes_pptx(tmp_path / "Deck.pptx")))
    assert doc.source_type == "pptx"
    assert [s.slide for s in doc.segments] == [1, 2]
    first = doc.segments[0]
    assert first.heading == ("Slide 1: RANSAC",)
    assert "Robust model fitting" in first.text and "Speaker notes: Mention inliers" in first.text


# ---- dispatcher --------------------------------------------------------------------------

def test_load_source_rejects_unknown_and_legacy_types(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.ppt").write_bytes(b"x")
    with pytest.raises(IngestError, match="Unsupported file type"):
        load_source(str(tmp_path / "a.txt"))
    with pytest.raises(IngestError, match="Re-save .* as .pptx"):
        load_source(str(tmp_path / "b.ppt"))
    with pytest.raises(IngestError, match="File not found"):
        load_source(str(tmp_path / "nope.pdf"))
    with pytest.raises(IngestError, match="Only YouTube"):
        load_source("https://example.com/page")


# ---- YouTube -----------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=tVskbekONlw&list=PPSV",
    "https://youtu.be/tVskbekONlw?t=30",
    "https://m.youtube.com/watch?v=tVskbekONlw",
    "https://www.youtube.com/shorts/tVskbekONlw",
    "https://www.youtube.com/embed/tVskbekONlw",
])
def test_parse_video_id(url):
    assert youtube_loader.parse_video_id(url) == "tVskbekONlw"


@pytest.mark.parametrize("url", ["https://www.youtube.com/watch", "https://youtube.com/watch?v=short",
                                 "https://www.youtube.com/"])
def test_parse_video_id_rejects_bad_urls(url):
    with pytest.raises(IngestError):
        youtube_loader.parse_video_id(url)


def test_is_youtube_url():
    assert youtube_loader.is_youtube_url("https://youtu.be/abc")
    assert not youtube_loader.is_youtube_url("https://vimeo.com/1")


def test_load_youtube_from_cache_cleans_and_flags_generated(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_loader, "_fetch_title", lambda vid: "A Lecture")
    cache = tmp_path / "transcripts"
    cache.mkdir()
    (cache / "tVskbekONlw.json").write_text(json.dumps({
        "generated": True,
        "snippets": [
            {"text": "[Music]", "start": 0.0, "duration": 2.0},
            {"text": "it&#39;s a\nhistogram", "start": 2.0, "duration": 3.0},
            {"text": "Otsu picks it", "start": 5.0, "duration": 2.0},
        ]}), encoding="utf-8")
    doc = youtube_loader.load_youtube("https://youtu.be/tVskbekONlw", cache_dir=tmp_path)
    assert doc.title == "A Lecture" and doc.source == "https://www.youtube.com/watch?v=tVskbekONlw"
    assert [s.text for s in doc.segments] == ["it's a histogram", "Otsu picks it"]
    assert doc.segments[0].t_start == 2.0 and doc.segments[0].t_end == 5.0
    assert doc.warnings and "Auto-generated" in doc.warnings[0]
