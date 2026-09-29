"""OKF Models — Pydantic schemas for Open Knowledge Format nodes."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


NODE_TYPES = Literal["concept", "definition", "procedure", "formula", "example", "summary"]


@dataclass
class OKFNode:
    """One structured knowledge unit extracted from a document."""
    type: str                        # concept | definition | procedure | formula | example | summary
    title: str                       # short headline
    description: str                 # one-sentence summary
    body: str                        # full explanation (markdown)
    tags: list[str] = field(default_factory=list)
    page_refs: list[int] = field(default_factory=list)
    trust: str = "high"              # high | medium | low
    source_document: str = ""        # document title
    document_id: int = 0
    collection_id: int = 0
    user_id: int = 0
    node_id: int = 0                 # set after DB insert


@dataclass
class OKFSearchResult:
    """A knowledge node with its similarity score."""
    node: OKFNode
    score: float
