from __future__ import annotations

from dataclasses import dataclass

from .admission import admit
from .differential import compare
from .epoch import InvalidationEpoch
from .identity import Subject
from .receipt import Receipt, issue
from .selector import select_store
from .strategies import RolloverStrategy, evaluate
from .witness import Witness


@dataclass(frozen=True)
class Qualification:
    strategy: RolloverStrategy
    standing: str
    store: str
    receipt: Receipt


def qualify(epoch: InvalidationEpoch, consumers: tuple[Subject, ...], witnesses: tuple[Witness, ...], strategy: RolloverStrategy, critical: frozenset[str] = frozenset(), *, durable: bool = False, transactional: bool = False) -> Qualification:
    admitted = admit(epoch, consumers, witnesses)
    keys = tuple(c.key for c in consumers)
    result = evaluate(strategy, admitted.frontier, keys, critical)
    _ = compare(admitted.frontier, keys, critical)
    store = select_store(durable=durable, transactional=transactional)
    standing = "PARTIAL_ALIVE" if result.complete else "UNKNOWN"
    receipt = issue({"producer": epoch.producer.key, "generation": epoch.generation, "event_id": epoch.event_id, "strategy": strategy.value, "standing": standing, "store": store.kind.value})
    return Qualification(strategy, standing, store.kind.value, receipt)


def require_do() -> None:
    raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")
