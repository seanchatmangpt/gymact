from __future__ import annotations

from dataclasses import dataclass

from .admission import AdmissionResult, admit_candidates
from .currentness import ProjectionEpoch
from .pareto import frontier
from .receipt import ProjectionReceipt, require_do
from .representation import RepresentationCandidate
from .roundtrip import RoundTripWitness
from .selectors import Score, SelectorKind, score, select
from .semantic_type import SemanticType
from .storage import StorageCapability, select_storage
from .subject import Subject


@dataclass(frozen=True, slots=True)
class ProjectionPlan:
    admission: AdmissionResult
    scores: tuple[Score, ...]
    pareto: tuple[Score, ...]
    selected: Score
    storage: StorageCapability
    receipt: ProjectionReceipt


def construct_plan(
    *,
    subject: Subject,
    semantic_type: SemanticType,
    candidates: tuple[RepresentationCandidate, ...],
    witnesses: tuple[RoundTripWitness, ...],
    epoch: ProjectionEpoch,
    selector: SelectorKind,
    require_lossless: bool = False,
    durable: bool = True,
    transactional: bool = False,
    action: str = "CONSTRUCT",
) -> ProjectionPlan:
    if action == "DO":
        require_do()
    admission = admit_candidates(
        semantic_type,
        candidates,
        witnesses,
        require_lossless=require_lossless,
    )
    by_fingerprint = {w.via_fingerprint: w for w in witnesses}
    scores = tuple(
        score(candidate, by_fingerprint.get(candidate.fingerprint))
        for candidate in admission.admitted
    )
    pareto = frontier(scores)
    selected = select(selector, pareto or scores)
    storage = select_storage(durable=durable, transactional=transactional)
    standing = "REQUALIFYING" if selected.fidelity_loss > 0 else "PARTIAL_ALIVE"
    receipt = ProjectionReceipt(
        subject=subject,
        semantic_iri=semantic_type.iri,
        selected_fingerprint=selected.candidate.fingerprint,
        selector=selector.value,
        epoch_token=epoch.token,
        storage=storage.kind.value,
        standing=standing,
    )
    return ProjectionPlan(admission, scores, pareto, selected, storage, receipt)
