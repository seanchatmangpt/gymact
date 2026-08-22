from __future__ import annotations

from dataclasses import dataclass

from .explore_ack_admission import admit
from .explore_ack_authority import Authority, Phase, admit_phase
from .explore_ack_comparator import Result, evaluate, pareto
from .explore_ack_identity import Subject
from .explore_ack_invalidation import Invalidation
from .explore_ack_protocols import Protocol, candidates
from .explore_ack_receipt import Receipt, make_receipt
from .explore_ack_witness import Witness


@dataclass(frozen=True)
class Qualification:
    alternatives: tuple[Result, ...]
    frontier: tuple[Result, ...]
    selected: Result
    receipt: Receipt


def qualify(
    event: Invalidation,
    consumers: tuple[Subject, ...],
    witnesses: tuple[Witness, ...],
    critical: frozenset[str],
    authority: Authority,
) -> Qualification:
    admit_phase(authority, Phase.SELECT)
    admitted = admit(event, consumers, witnesses)
    protocols: tuple[Protocol, ...] = candidates(len(consumers), critical)
    keys = frozenset(consumer.key for consumer in consumers)
    results = tuple(evaluate(protocol, admitted.frontier, keys) for protocol in protocols)
    frontier = pareto(results)
    selected = sorted(
        frontier,
        key=lambda result: (not result.safe, not result.complete, result.protocol),
    )[0]
    admit_phase(authority, Phase.CONSTRUCT)
    evidence = repr((event, admitted.frontier, results)).encode()
    receipt = make_receipt(event.producer.key, event.event_id, selected, evidence)
    return Qualification(results, frontier, selected, receipt)
