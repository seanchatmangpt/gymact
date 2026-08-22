from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .compatibility import CompatibilityWitness
from .context import SelectionContext
from .frontier import resolve
from .intent import SelectionIntent
from .receipt import QualificationReceipt, manufacture
from .storage import StoreCandidate, select
from .strategies import FreshnessDecision, FreshnessStrategy, decide


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def require(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")


@dataclass(frozen=True, slots=True)
class Qualification:
    decision: FreshnessDecision
    store: StoreCandidate
    receipt: QualificationReceipt


def qualify(
    *,
    intents: tuple[SelectionIntent, ...],
    before: SelectionContext,
    after: SelectionContext,
    strategy: FreshnessStrategy,
    now: datetime,
    witness: CompatibilityWitness | None = None,
    durable: bool = False,
    transactional: bool = False,
) -> Qualification:
    require(ActionClass.CONSTRUCT)
    frontier = resolve(intents, now)
    if frontier.current is None:
        raise ValueError("REFUSED_NO_ACTIVE_INTENT")
    if frontier.current.context != before:
        raise ValueError("REFUSED_INTENT_CONTEXT_MISMATCH")
    decision = decide(strategy, before, after, witness)
    store = select(durable=durable, transactional=transactional)
    receipt = manufacture(
        {
            "subject": before.subject.identity,
            "intent_nonce": frontier.current.nonce,
            "before": before.fingerprint,
            "after": after.fingerprint,
            "strategy": strategy.value,
            "standing": decision.standing,
            "reusable": decision.reusable,
            "store": store.kind.value,
        }
    )
    return Qualification(decision, store, receipt)
