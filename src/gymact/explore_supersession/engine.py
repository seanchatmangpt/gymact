from __future__ import annotations

from dataclasses import dataclass

from .admission import admit
from .candidates import Candidate, default_candidates
from .discovery import discover
from .evidence import Evidence
from .frontier import Frontier, resolve_frontier
from .receipt import Receipt, make_receipt
from .selection import weighted_select
from .subject import Refusal, Subject
from .supersession import Supersession


@dataclass(frozen=True)
class Qualification:
    subject: Subject
    frontier: Frontier
    candidate: Candidate
    receipt: Receipt
    actuation_performed: bool = False


def require_authority(action: str) -> None:
    allowed = {"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"}
    if action not in allowed:
        raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")


def qualify(
    subject: Subject,
    evidence: list[Evidence],
    edges: tuple[Supersession, ...],
    required: frozenset[str] = frozenset({"replay"}),
) -> Qualification:
    require_authority("SELECT")
    admitted = admit(subject, evidence)
    frontier = resolve_frontier(admitted, edges)
    viable = discover(default_candidates(), required)
    scores = {candidate.name: (len(candidate.capabilities), int(candidate.storage != "memory")) for candidate in viable}
    candidate = weighted_select(viable, scores, (3, 1))
    require_authority("CONSTRUCT")
    receipt = make_receipt(subject, frontier)
    return Qualification(subject, frontier, candidate, receipt)
