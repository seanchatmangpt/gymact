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


def evaluate(
    protocol: Protocol,
    frontier: dict[str, WitnessKind],
    all_consumers: frozenset[str],
) -> Result:
    acked = {
        key
        for key, value in frontier.items()
        if value in {WitnessKind.ACKNOWLEDGED, WitnessKind.DISCHARGED}
    }
    discharged = {key for key, value in frontier.items() if value is WitnessKind.DISCHARGED}
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
    return tuple(
        result
        for result in results
        if not any(
            other != result
            and other.safe >= result.safe
            and other.complete >= result.complete
            and other.acknowledged >= result.acknowledged
            and other.discharged >= result.discharged
            and (
                other.safe > result.safe
                or other.complete > result.complete
                or other.acknowledged > result.acknowledged
                or other.discharged > result.discharged
            )
            for other in results
        )
    )
