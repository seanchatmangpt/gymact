from __future__ import annotations
from dataclasses import dataclass
from .explore_ack_protocols import Protocol, ProtocolKind
from .explore_ack_witness import WitnessKind

@dataclass(frozen=True, order=True)
class Result:
    safe: bool
    complete: bool
    acknowledged: int
    discharged: int
    protocol: str

def evaluate(protocol: Protocol, frontier: dict[str, WitnessKind], all_consumers: frozenset[str]) -> Result:
    acked = {k for k, v in frontier.items() if v in {WitnessKind.ACKNOWLEDGED, WitnessKind.DISCHARGED}}
    discharged = {k for k, v in frontier.items() if v is WitnessKind.DISCHARGED}
    if protocol.kind is ProtocolKind.ALL:
        complete = discharged == all_consumers
        safe = acked == all_consumers
    elif protocol.kind is ProtocolKind.QUORUM:
        complete = len(discharged) >= protocol.quorum
        safe = len(acked) >= protocol.quorum
    else:
        complete = protocol.critical_consumers <= discharged
        safe = protocol.critical_consumers <= acked
    return Result(safe, complete, len(acked), len(discharged), protocol.kind.value)

def pareto(results: tuple[Result, ...]) -> tuple[Result, ...]:
    return tuple(r for r in results if not any(
        other != r and other.safe >= r.safe and other.complete >= r.complete
        and other.acknowledged >= r.acknowledged and other.discharged >= r.discharged
        and (other.safe > r.safe or other.complete > r.complete
             or other.acknowledged > r.acknowledged or other.discharged > r.discharged)
        for other in results
    ))
