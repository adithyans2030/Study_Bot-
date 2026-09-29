"""Structure-aware chunking.

Documents with headings: one chunk per section, long sections split on paragraph/sentence
boundaries with overlap, and tiny neighbouring sections merged. Slides: one chunk per slide.
Transcripts: ~90 second windows with overlap. Every chunk carries a
'Document › Heading' header that is prepended when embedding.

Token counts are estimates (words x 1.3); the embedder truncates at 512 real tokens, so the
default max stays well below that.
"""
import re
from dataclasses import dataclass, field

from app.ingest.types import Chunk, LoadedDocument, Segment

_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3) + 1


@dataclass(frozen=True)
class ChunkingConfig:
    target_tokens: int = 320
    max_tokens: int = 420
    min_tokens: int = 80
    overlap_tokens: int = 40
    window_seconds: float = 90.0


@dataclass
class _Unit:
    """Text destined for one chunk. `sections` keeps (heading path, text) pairs so merged
    units can label each part."""
    sections: list[tuple[tuple[str, ...], str]]
    pages: list[int] = field(default_factory=list)
    slides: list[int] = field(default_factory=list)
    split: bool = False

    @property
    def tokens(self) -> int:
        return sum(approx_tokens(text) for _, text in self.sections)


def _pieces(text: str, max_tokens: int) -> list[str]:
    """Break an oversized block into sentence-sized pieces, hard-splitting any overlong sentence."""
    out: list[str] = []
    step = max(1, int(max_tokens / 1.3))
    for part in _SPLIT.split(text):
        part = part.strip()
        if not part:
            continue
        if approx_tokens(part) <= max_tokens:
            out.append(part)
        else:
            words = part.split()
            out.extend(" ".join(words[i:i + step]) for i in range(0, len(words), step))
    return out


def _group_sections(segments: list[Segment]) -> list[list[Segment]]:
    groups: list[list[Segment]] = []
    last_key = None
    for seg in segments:
        key = (seg.heading, seg.slide)
        if groups and key == last_key:
            groups[-1].append(seg)
        else:
            groups.append([seg])
            last_key = key
    return groups


def _section_units(group: list[Segment], cfg: ChunkingConfig) -> list[_Unit]:
    heading = group[0].heading
    slide = group[0].slide
    total = sum(approx_tokens(seg.text) for seg in group)
    if total <= cfg.max_tokens:
        text = "\n".join(seg.text for seg in group)
        pages = [seg.page for seg in group if seg.page is not None]
        return [_Unit([(heading, text)], pages, [slide] if slide is not None else [])]

    units: list[_Unit] = []
    current: list[str] = []
    carried = 0  # leading pieces in `current` that are overlap copied from the previous chunk
    current_tokens = 0
    current_pages: list[int] = []

    def flush():
        nonlocal current, carried, current_tokens, current_pages
        units.append(_Unit([(heading, "\n".join(current))], list(current_pages),
                           [slide] if slide is not None else [], split=True))
        tail: list[str] = []
        tail_tokens = 0
        for piece in reversed(current):
            t = approx_tokens(piece)
            if tail_tokens + t > cfg.overlap_tokens:
                break
            tail.insert(0, piece)
            tail_tokens += t
        current, carried, current_tokens = tail, len(tail), tail_tokens
        current_pages = current_pages[-1:] if tail else []

    for seg in group:
        blocks = [seg.text] if approx_tokens(seg.text) <= cfg.max_tokens else _pieces(seg.text, cfg.max_tokens)
        for block in blocks:
            t = approx_tokens(block)
            if len(current) > carried and current_tokens + t > cfg.target_tokens:
                flush()
            current.append(block)
            current_tokens += t
            if seg.page is not None and seg.page not in current_pages:
                current_pages.append(seg.page)
    if len(current) > carried:  # anything beyond bare overlap is new text and must be kept
        flush()
    return units


def _common_prefix(paths: list[tuple[str, ...]]) -> tuple[str, ...]:
    prefix = paths[0]
    for path in paths[1:]:
        n = 0
        while n < min(len(prefix), len(path)) and prefix[n] == path[n]:
            n += 1
        prefix = prefix[:n]
    return prefix


def _merge(a: _Unit, b: _Unit) -> _Unit:
    return _Unit(a.sections + b.sections, a.pages + b.pages, a.slides + b.slides)


def _to_chunk(ordinal: int, title: str, unit: _Unit) -> Chunk:
    prefix = _common_prefix([path for path, _ in unit.sections])
    parts: list[str] = []
    for path, text in unit.sections:
        tail = path[len(prefix):]
        if tail:
            parts.append(" › ".join(tail))
        parts.append(text)
    meta: dict = {"heading": list(prefix)}
    if unit.pages:
        meta["page_start"], meta["page_end"] = min(unit.pages), max(unit.pages)
    if unit.slides:
        meta["slide"] = unit.slides[0]
        meta["slides"] = sorted(set(unit.slides))
    return Chunk(ordinal=ordinal, header=" › ".join([title, *prefix]), text="\n".join(parts), meta=meta)


def _chunk_structured(doc: LoadedDocument, cfg: ChunkingConfig) -> list[Chunk]:
    units: list[_Unit] = []
    for group in _group_sections(doc.segments):
        units.extend(_section_units(group, cfg))

    same_parent_only = doc.source_type != "pptx"
    merged: list[_Unit] = []
    for unit in units:
        prev = merged[-1] if merged else None
        if (prev is not None and not prev.split and not unit.split
                and prev.tokens < cfg.min_tokens
                and prev.tokens + unit.tokens <= cfg.target_tokens
                and (not same_parent_only or prev.sections[0][0][:1] == unit.sections[0][0][:1])):
            merged[-1] = _merge(prev, unit)
        else:
            merged.append(unit)
    return [_to_chunk(i, doc.title, unit) for i, unit in enumerate(merged)]


def _chunk_transcript(doc: LoadedDocument, cfg: ChunkingConfig) -> list[Chunk]:
    segs = doc.segments
    chunks: list[Chunk] = []
    i = 0
    while i < len(segs):
        j, tokens, start = i, 0, segs[i].t_start
        while j < len(segs):
            t = approx_tokens(segs[j].text)
            if j > i and (tokens + t > cfg.target_tokens or segs[j].t_end - start > cfg.window_seconds):
                break
            tokens += t
            j += 1
        chunks.append(Chunk(
            ordinal=len(chunks),
            header=doc.title,
            text=" ".join(s.text for s in segs[i:j]),
            meta={"t_start": segs[i].t_start, "t_end": segs[j - 1].t_end},
        ))
        if j >= len(segs):
            break
        threshold = segs[j - 1].t_end - cfg.window_seconds * 0.15
        back = j
        while back - 1 > i and segs[back - 1].t_start >= threshold:
            back -= 1
        i = max(back, i + 1)
    return chunks


def chunk_document(doc: LoadedDocument, cfg: ChunkingConfig | None = None) -> list[Chunk]:
    cfg = cfg or ChunkingConfig()
    if doc.source_type == "youtube":
        return _chunk_transcript(doc, cfg)
    return _chunk_structured(doc, cfg)
