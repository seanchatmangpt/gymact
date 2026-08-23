from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StoreKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True, slots=True)
class StoreCandidate:
    kind: StoreKind
    durable: bool
    transactional: bool


CANDIDATES = (
    StoreCandidate(StoreKind.MEMORY, False, False),
    StoreCandidate(StoreKind.JSONL, True, False),
    StoreCandidate(StoreKind.SQLITE, True, True),
)


def discover(*, durable: bool = False, transactional: bool = False) -> tuple[StoreCandidate, ...]:
    return tuple(
        candidate
        for candidate in CANDIDATES
        if (not durable or candidate.durable)
        and (not transactional or candidate.transactional)
    )


def select(*, durable: bool = False, transactional: bool = False) -> StoreCandidate:
    viable = discover(durable=durable, transactional=transactional)
    return sorted(
        viable,
        key=lambda candidate: (candidate.durable, candidate.transactional, candidate.kind.value),
    )[0]
