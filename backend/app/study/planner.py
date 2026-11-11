"""Exam-driven study plan builder: pure domain logic, no DB/HTTP access, unit-testable directly."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.okf.models import OKFNode
from app.study.attempts_store import NodeAttemptStats

WEAK_ACCURACY_THRESHOLD = 0.6
MAX_PLAN_DAYS = 30


@dataclass(frozen=True)
class PlannedNode:
    node_id: int
    title: str
    type: str
    source_document: str
    status: str  # untested | weak | known
    accuracy: float | None
    last_attempt_at: float | None


@dataclass(frozen=True)
class PlannedDay:
    date: date
    day_index: int
    nodes: list[PlannedNode]


@dataclass(frozen=True)
class StudyPlan:
    deadline: date
    days_remaining: int
    days: list[PlannedDay]


def _status(stats: NodeAttemptStats | None) -> str:
    if stats is None:
        return "untested"
    return "weak" if stats.accuracy < WEAK_ACCURACY_THRESHOLD else "known"


def _sort_key(node: OKFNode, stats: NodeAttemptStats | None) -> tuple:
    """Untested first; then weak, worst accuracy then oldest attempt; then known, staled-longest
    first. The resulting order is sliced into consecutive day-buckets, so this key alone decides
    which day a node lands on - untested/weak nodes end up in the earliest (highest-priority) days."""
    if stats is None:
        return (0, 0.0, 0.0)
    if stats.accuracy < WEAK_ACCURACY_THRESHOLD:
        return (1, stats.accuracy, -stats.last_attempt_at)
    return (2, 0.0, -stats.last_attempt_at)


def _chunk(items: list, n: int) -> list[list]:
    """Split into n consecutive slices of near-equal size; earlier slices absorb any remainder,
    so the (already priority-sorted) front of the list never gets diluted into a later day."""
    size, remainder = divmod(len(items), n)
    chunks, start = [], 0
    for i in range(n):
        length = size + (1 if i < remainder else 0)
        chunks.append(items[start:start + length])
        start += length
    return chunks


def build_plan(nodes: list[OKFNode], stats: dict[int, NodeAttemptStats],
               today: date, deadline: date) -> StudyPlan:
    """Rank nodes untested-first, then weakest/oldest, then known-but-staled, and bucket them into
    consecutive days up to `deadline` - day 1 gets the highest-priority slice, front-loading the
    riskiest gaps rather than saving them for the last day."""
    ranked = sorted(nodes, key=lambda n: _sort_key(n, stats.get(n.node_id)))

    days_remaining = max((deadline - today).days, 0)
    bucket_days = min(max(days_remaining, 1), MAX_PLAN_DAYS)

    days = []
    for day_index, bucket in enumerate(_chunk(ranked, bucket_days)):
        planned = []
        for node in bucket:
            node_stats = stats.get(node.node_id)
            planned.append(PlannedNode(
                node_id=node.node_id, title=node.title, type=node.type,
                source_document=node.source_document, status=_status(node_stats),
                accuracy=node_stats.accuracy if node_stats else None,
                last_attempt_at=node_stats.last_attempt_at if node_stats else None,
            ))
        days.append(PlannedDay(date=today + timedelta(days=day_index), day_index=day_index, nodes=planned))

    return StudyPlan(deadline=deadline, days_remaining=days_remaining, days=days)
