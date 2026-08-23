from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from .authority import ActionClass, admit_action
from .diagnostics import WeightDiagnostics, diagnose
from .direct import ModelPrediction
from .failure import FailureWorld
from .logged import LoggedDecision
from .pareto import EvaluationVector, frontier
from .receipt import EvaluationReceipt, issue
from .shift import total_variation
from .storage import StorageCandidate
from .storage import select as select_storage
from .strategies import OPEStrategy, evaluate
from .subject import Subject
from .support import SupportSummary, summarize


@dataclass(frozen=True, slots=True)
class Qualification:
    subject: Subject
    selected: EvaluationVector
    alternatives: tuple[EvaluationVector, ...]
    support: SupportSummary
    diagnostics: WeightDiagnostics
    storage: StorageCandidate
    standing: str
    receipt: EvaluationReceipt
    actuation_performed: bool = False


def _standing(
    support: SupportSummary,
    diagnostics: WeightDiagnostics,
    shift: Fraction,
    failure_world: FailureWorld | None,
) -> str:
    if failure_world and failure_world.hidden_confounding_flag:
        return "UNKNOWN"
    if support.support_ratio < 1:
        return "UNKNOWN"
    if diagnostics.effective_sample_ratio < Fraction(1, 3):
        return "REQUALIFYING"
    if shift > Fraction(1, 2):
        return "REQUALIFYING"
    return "PARTIAL_ALIVE"


def qualify(
    *,
    subject: Subject,
    decisions: Iterable[LoggedDecision],
    predictions: Iterable[ModelPrediction] = (),
    clip: Fraction = Fraction(3),
    durable: bool = False,
    transactional: bool = False,
    failure_world: FailureWorld | None = None,
) -> Qualification:
    admit_action(ActionClass.CONSTRUCT)
    rows = tuple(decisions)
    prediction_rows = tuple(predictions)
    support = summarize(rows)
    diagnostics = diagnose(rows)
    shift = total_variation(rows)
    strategies = [
        OPEStrategy.IPS,
        OPEStrategy.SNIPS,
        OPEStrategy.CLIPPED_IPS,
    ]
    if prediction_rows:
        strategies.extend((OPEStrategy.DIRECT_MODEL, OPEStrategy.DOUBLY_ROBUST))
    vectors = tuple(
        EvaluationVector(
            strategy=strategy,
            estimate=evaluate(
                strategy,
                rows,
                predictions=prediction_rows,
                clip=clip,
            ),
            support_ratio=support.support_ratio,
            effective_sample_ratio=diagnostics.effective_sample_ratio,
            max_weight=diagnostics.max_weight,
            shift=shift,
        )
        for strategy in strategies
    )
    alternatives = frontier(vectors)
    selected = min(
        alternatives,
        key=lambda row: (
            -row.support_ratio,
            -row.effective_sample_ratio,
            row.shift,
            row.max_weight,
            row.strategy.value,
        ),
    )
    storage = select_storage(durable=durable, transactional=transactional)
    standing = _standing(support, diagnostics, shift, failure_world)
    receipt = issue(
        subject=subject,
        strategy=selected.strategy.value,
        estimate=selected.estimate,
        standing=standing,
        storage=storage.kind.value,
    )
    return Qualification(
        subject=subject,
        selected=selected,
        alternatives=alternatives,
        support=support,
        diagnostics=diagnostics,
        storage=storage,
        standing=standing,
        receipt=receipt,
    )
