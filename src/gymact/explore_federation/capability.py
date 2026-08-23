from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    id: str
    capabilities: frozenset[str]
    reversible: bool = True


def discover(candidates: list[Candidate], required: set[str]) -> tuple[Candidate, ...]:
    return tuple(
        sorted(
            (candidate for candidate in candidates if required <= candidate.capabilities),
            key=lambda candidate: candidate.id,
        )
    )
