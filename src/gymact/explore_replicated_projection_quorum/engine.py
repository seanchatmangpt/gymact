from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

from .admission import admit_observations
from .audit import audit_root
from .causality import causal_profile
from .quorum import QuorumAssessment, assess_quorum
from .receipt import ActionClass, QualificationReceipt, require_action
from .refusal import Refused
from .replica import ReplicaProjection
from .selectors import Selection, SelectorKind, select
from .storage import StorageCapability, choose_storage
from .subject import Subject
from .universe import ReplicaUniverse
from .window import ObservationWindow


@dataclass(frozen=True, slots=True)
class Qualification:
    assessment: QuorumAssessment
    selection: Selection | None
    storage: StorageCapability
    receipt: QualificationReceipt


def qualify(
    observations: tuple[ReplicaProjection, ...],
    *,
    subject: Subject,
    semantic_digest: str,
    universe: ReplicaUniverse,
    window: ObservationWindow,
    now: datetime,
    selector: SelectorKind,
    durable: bool = False,
    transactional: bool = False,
    action: ActionClass = ActionClass.CONSTRUCT,
) -> Qualification:
    require_action(action)
    admitted = admit_observations(
        observations,
        subject=subject,
        semantic_digest=semantic_digest,
        universe=universe,
        window=window,
        now=now,
    )
    assessment = assess_quorum(admitted, universe)
    selection: Selection | None = None
    if assessment.state.value == "HEALTHY":
        selection = select(selector, admitted, universe)
    storage = choose_storage(durable=durable, transactional=transactional)
    profile = causal_profile(admitted)
    body = {
        "action": action.value,
        "agreeing_replicas": assessment.agreeing_replicas,
        "audit_root": audit_root(admitted),
        "causal_maxima": profile.maximal_replica_ids,
        "concurrency_ratio": str(profile.concurrency_ratio),
        "coverage": str(assessment.coverage),
        "semantic_digest": semantic_digest,
        "selected_generation": selection.generation if selection else None,
        "selected_projection_digest": selection.projection_digest if selection else None,
        "selector": selector.value,
        "standing": assessment.standing,
        "storage": storage.kind.value,
        "subject": subject.value,
    }
    return Qualification(assessment, selection, storage, QualificationReceipt.create(body))


def compare_selection_geometry(
    selection: Selection, *, highest_generation: int, conflict_fraction: Fraction
) -> tuple[Fraction, Fraction, int]:
    if highest_generation < selection.generation:
        raise Refused("REFUSED_INVALID_FRESHNESS_REFERENCE")
    return selection.coverage, conflict_fraction, highest_generation - selection.generation
