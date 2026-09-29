"""Data shapes shared by loaders, the chunker and the store."""
from dataclasses import dataclass, field


class IngestError(Exception):
    """A source could not be loaded. The message is safe to show to the user."""


@dataclass
class Segment:
    """One unit of extracted text (paragraph, table, slide, caption line) with its location."""
    text: str
    heading: tuple[str, ...] = ()
    page: int | None = None
    slide: int | None = None
    t_start: float | None = None
    t_end: float | None = None


@dataclass
class LoadedDocument:
    title: str
    source_type: str  # pdf | pptx | docx | youtube
    source: str  # absolute path or canonical URL
    content_hash: str
    segments: list[Segment]
    warnings: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    ordinal: int
    header: str  # "Doc title › Heading › Subheading", prepended when embedding
    text: str
    meta: dict
