from __future__ import annotations

from dataclasses import dataclass

from .subject import Refusal


@dataclass(frozen=True, order=True)
class Candidate:
    name: str
    semantic: str
    storage: str
    runtime: str
    capabilities: frozenset[str]
    reversible: bool = True

    def __post_init__(self) -> None:
        if not self.reversible:
            raise Refusal("REFUSED_IRREVERSIBLE_EXPLORE_CANDIDATE")


def default_candidates() -> tuple[Candidate, ...]:
    return (
        Candidate("memory-local", "exact-frontier", "memory", "local", frozenset({"replay", "failure"})),
        Candidate("jsonl-local", "exact-frontier", "jsonl", "local", frozenset({"replay", "durable"})),
        Candidate("graph-local", "supersession-graph", "memory", "local", frozenset({"replay", "topology"})),
    )
