from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Mapping

DIMENSIONS = ("semantic", "avatar", "context", "evidence", "materiality", "grammar")


@dataclass(frozen=True, slots=True)
class PresentationCandidate:
    identity: str
    scores: tuple[int, int, int, int, int, int]
    projected_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.scores) != len(DIMENSIONS):
            raise ValueError("candidate must score every DfCM dimension")


@dataclass(frozen=True, slots=True)
class ScreenReceipt:
    grammar_digest: str
    world_digest: str
    input_digest: str
    frontier_digest: str
    screen_digest: str
    irreversible_selections: int = 0


@dataclass(frozen=True, slots=True)
class IntentReceipt:
    screen_digest: str
    claim: str
    action: str
    actuation: bool = False


def _dominates(left: PresentationCandidate, right: PresentationCandidate) -> bool:
    ge = all(a >= b for a, b in zip(left.scores, right.scores, strict=True))
    gt = any(a > b for a, b in zip(left.scores, right.scores, strict=True))
    return ge and gt


def pareto_frontier(candidates: Iterable[PresentationCandidate]) -> tuple[PresentationCandidate, ...]:
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.identity))
    return tuple(
        candidate
        for candidate in ordered
        if not any(_dominates(other, candidate) for other in ordered if other != candidate)
    )


def deterministic_select(frontier: Iterable[PresentationCandidate]) -> PresentationCandidate:
    ordered = tuple(sorted(frontier, key=lambda candidate: (candidate.scores, candidate.identity), reverse=True))
    if not ordered:
        raise ValueError("presentation frontier is empty")
    return ordered[0]


def digest(parts: Iterable[str]) -> str:
    payload = "\x1f".join(parts).encode()
    return sha256(payload).hexdigest()


def make_screen_receipt(
    *, grammar: str, world: str, input_payload: str, frontier: Iterable[PresentationCandidate], screen: str
) -> ScreenReceipt:
    frontier_ids = tuple(candidate.identity for candidate in pareto_frontier(frontier))
    return ScreenReceipt(
        grammar_digest=digest((grammar,)),
        world_digest=digest((world,)),
        input_digest=digest((input_payload,)),
        frontier_digest=digest(frontier_ids),
        screen_digest=digest((screen,)),
    )


def make_intent(receipt: ScreenReceipt, claim: str, action: str, projected_actions: Iterable[str]) -> IntentReceipt:
    if action not in set(projected_actions):
        raise ValueError("REFUSED_UNPROJECTED_ACTION")
    return IntentReceipt(screen_digest=receipt.screen_digest, claim=claim, action=action)


def replay_matches(receipt: ScreenReceipt, observed: Mapping[str, str]) -> bool:
    expected = {
        "grammar_digest": receipt.grammar_digest,
        "world_digest": receipt.world_digest,
        "input_digest": receipt.input_digest,
        "frontier_digest": receipt.frontier_digest,
        "screen_digest": receipt.screen_digest,
    }
    return receipt.irreversible_selections == 0 and all(observed.get(key) == value for key, value in expected.items())
