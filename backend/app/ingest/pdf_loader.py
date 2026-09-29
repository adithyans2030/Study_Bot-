"""PDF loader (PyMuPDF).

Recovers structure from typography: bold text larger than the body is a heading (level by
size rank), tables become self-describing rows, and text repeated in the page margins on most
pages (footers, running headers) is dropped.

PyMuPDF is AGPL-licensed: fine for private/self-hosted use, but review before distributing.
"""
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.ingest.text_utils import clean_text, prettify_stem, render_table, sha256_file
from app.ingest.types import IngestError, LoadedDocument, Segment

_BULLET_CHARS = set("•●▪◦·*-–")
_MIN_TEXT_CHARS_PER_PAGE = 20
_MARGIN = 0.10  # top/bottom fraction of the page considered header/footer territory


@dataclass
class _Line:
    text: str
    size: float
    bold: bool
    block: int
    block_lines: int
    bbox: tuple[float, float, float, float]
    page_height: float


@dataclass
class _Table:
    bbox: tuple[float, float, float, float]
    text: str


def _is_bold(span: dict) -> bool:
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def _is_bullet_marker(raw: str) -> bool:
    stripped = raw.strip()
    return bool(stripped) and all(ch in _BULLET_CHARS or "" <= ch <= "" for ch in stripped)


def _inside(bbox, boxes, pad: float = 2.0) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return any(b[0] - pad <= cx <= b[2] + pad and b[1] - pad <= cy <= b[3] + pad for b in boxes)


def _extract_page(page) -> list[_Line | _Table]:
    tables: list[_Table] = []
    try:
        for table in page.find_tables().tables:
            text = render_table(table.extract())
            if text:
                tables.append(_Table(tuple(table.bbox), text))
    except Exception:
        tables = []  # odd page geometry: fall back to plain text flow for this page

    table_boxes = [t.bbox for t in tables]
    flow: list[_Line | _Table] = []
    for block_no, block in enumerate(page.get_text("dict")["blocks"]):
        if block["type"] != 0:
            continue
        lines = [ln for ln in block["lines"] if "".join(s["text"] for s in ln["spans"]).strip()]
        for line in lines:
            if _inside(line["bbox"], table_boxes):
                continue
            spans = [s for s in line["spans"] if s["text"].strip()]
            flow.append(_Line(
                text="".join(s["text"] for s in line["spans"]),
                size=round(max(s["size"] for s in spans), 1),
                bold=all(_is_bold(s) for s in spans),
                block=block_no,
                block_lines=len(lines),
                bbox=tuple(line["bbox"]),
                page_height=page.rect.height,
            ))

    # Place each table right after the last text line above it. Lines are NOT guaranteed to be
    # sorted by y: PyMuPDF often lists the page footer first, so "first line below the table"
    # would put every table at the top of the page.
    for table in sorted(tables, key=lambda t: t.bbox[1]):
        index = 0
        for i, item in enumerate(flow):
            if isinstance(item, _Line) and item.bbox[1] < table.bbox[1]:
                index = i + 1
        flow.insert(index, table)
    return flow


def _norm(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.strip().lower()))


def _margin_noise(pages: list[list[_Line | _Table]]) -> set[str]:
    """Text that sits in the top/bottom margin on at least half of the pages."""
    if len(pages) < 3:
        return set()
    seen: Counter[str] = Counter()
    for flow in pages:
        in_margin = {
            _norm(item.text) for item in flow
            if isinstance(item, _Line) and len(item.text) <= 120
            and (item.bbox[1] < _MARGIN * item.page_height or item.bbox[3] > (1 - _MARGIN) * item.page_height)
        }
        seen.update(in_margin)
    return {text for text, count in seen.items() if count >= max(3, len(pages) / 2)}


def _heading_levels(pages: list[list[_Line | _Table]], noise: set[str]) -> tuple[float, dict[float, int], float | None]:
    """Returns (body_size, {heading_size: level}, title_size). Level 0 is the document title."""
    weight: Counter[float] = Counter()
    bold_sizes: set[float] = set()
    for flow in pages:
        for item in flow:
            if isinstance(item, _Line) and _norm(item.text) not in noise:
                weight[item.size] += len(item.text.strip())
                if item.bold:
                    bold_sizes.add(item.size)
    if not weight:
        return 10.0, {}, None
    body = weight.most_common(1)[0][0]
    bigger = sorted((s for s in bold_sizes if s >= body + 0.5), reverse=True)
    title_size = bigger[0] if bigger and bigger[0] >= body * 1.6 else None
    levels = {}
    level = 1
    for size in bigger:
        if size == title_size:
            levels[size] = 0
        else:
            levels[size] = level
            level += 1
    minor_level = level  # bold text at body size, e.g. "1. Image Acquisition"
    levels[body] = minor_level
    return body, levels, title_size


def _heading_level(line: _Line, body: float, levels: dict[float, int]) -> int | None:
    if not line.bold:
        return None
    if line.size >= body + 0.5:
        return levels.get(line.size)
    text = line.text.strip()
    single_short_line = line.block_lines == 1 and len(text) <= 80 and not text.endswith((".", ":", ","))
    return levels.get(body) if single_short_line and any(ch.isalpha() for ch in text) else None


def load_pdf(path: str | Path) -> LoadedDocument:
    path = Path(path)
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # the library's message contains file paths, so it is not shown to users
        raise IngestError(f"Could not open PDF '{path.name}'. The file may be damaged.") from exc
    try:
        return _load_open_pdf(doc, path)
    finally:
        doc.close()  # Windows cannot delete a file that is still open (uploads are deleted later)


def _load_open_pdf(doc, path: Path) -> LoadedDocument:
    if doc.needs_pass:
        raise IngestError(f"'{path.name}' is password-protected.")

    pages = [_extract_page(page) for page in doc]
    noise = _margin_noise(pages)
    body, levels, _title_size = _heading_levels(pages, noise)

    segments: list[Segment] = []
    warnings: list[str] = []
    heading_path: list[str] = []

    for page_no, flow in enumerate(pages, start=1):
        paragraph: list[str] = []
        paragraph_block: int | None = None
        pending_bullet = False
        last_heading_block: int | None = None

        def flush():
            nonlocal paragraph, paragraph_block
            text = clean_text(" ".join(paragraph))
            if text:
                segments.append(Segment(text=text, heading=tuple(heading_path), page=page_no))
            paragraph, paragraph_block = [], None

        chars_on_page = 0
        for item in flow:
            if isinstance(item, _Table):
                flush()
                segments.append(Segment(text=item.text, heading=tuple(heading_path), page=page_no))
                chars_on_page += len(item.text)
                continue
            raw = item.text
            if _norm(raw) in noise:
                continue
            if _is_bullet_marker(raw):
                flush()
                pending_bullet = True
                continue
            text = clean_text(raw)
            if not text:
                continue
            chars_on_page += len(text)

            level = _heading_level(item, body, levels)
            if level is not None:
                flush()
                if level == 0:
                    continue  # document title line: the filename-derived title is used instead
                if last_heading_block == item.block and heading_path:
                    heading_path[-1] = f"{heading_path[-1]} {text}"  # wrapped heading line
                else:
                    del heading_path[level - 1:]
                    heading_path.append(text)
                last_heading_block = item.block
                continue

            last_heading_block = None
            if pending_bullet or (paragraph_block is not None and item.block != paragraph_block):
                flush()
            if not paragraph:
                paragraph_block = item.block
                if pending_bullet:
                    text = "- " + text
                    pending_bullet = False
            paragraph.append(text)
        flush()

        if chars_on_page < _MIN_TEXT_CHARS_PER_PAGE:
            warnings.append(f"Page {page_no} has almost no extractable text (scanned image?). OCR is not supported yet.")

    if not any(seg.text.strip() for seg in segments):
        raise IngestError(f"No extractable text in '{path.name}'. It may be a scanned PDF (OCR is not supported yet).")

    return LoadedDocument(
        title=prettify_stem(path),
        source_type="pdf",
        source=str(path.resolve()),
        content_hash=sha256_file(path),
        segments=segments,
        warnings=warnings,
    )
