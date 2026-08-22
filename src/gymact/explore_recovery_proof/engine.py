from __future__ import annotations

from dataclasses import dataclass

from .admission import admit
from .attempt import RecoveryAttempt
from .authority import ActionClass, require
from .comparison import pareto
from .context import RecoveryContext
from .receipt import Receipt, issue
from .storage import StoreCandidate, select
from .strategies import RecoveryProtocol
from .topology import DependencyGraph
from .witness import CompatibilityWitness


@dataclass(frozen=True, slots=True)
class Qualification:
    standing: str
    protocol: RecoveryProtocol
    store: StoreCandidate
    receipt: Receipt


def qualify(
    *,
    attempt: RecoveryAttempt,
    base: RecoveryContext,
    target: RecoveryContext,
    current: RecoveryContext,
    protocol: RecoveryProtocol,
    dependency_graph: DependencyGraph,
    standings: dict[str, str],
    witness: CompatibilityWitness | None = None,
    durable: bool = False,
    transactional: bool = False,
) -> Qualification:
    require(ActionClass.CONSTRUCT)
    blockers = dependency_graph.blockers(standings)
    root = current.subject.identity
    if blockers.get(root):
        standing = "BLOCKED"
        reason = "DEPENDENCY_BLOCKED"
    else:
        decision = admit(attempt, base, target, current, protocol, witness)
        standing = decision.standing
        reason = decision.reason
    store = select(durable=durable, transactional=transactional)
    receipt = issue(
        {
            "subject": root,
            "attempt": attempt.identity,
            "protocol": protocol.value,
            "standing": standing,
            "reason": reason,
            "store": store.kind.value,
            "pareto": [score.protocol.value for score in pareto()],
        }
    )
    return Qualification(standing, protocol, store, receipt)
