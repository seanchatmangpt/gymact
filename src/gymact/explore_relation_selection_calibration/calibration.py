from __future__ import annotations

from dataclasses import dataclass

from .errors import Refused
from .relation import Relation
from .subject import Subject


@dataclass(frozen=True)
class CalibrationEvidence:
    subject: Subject
    relation: Relation
    generation: int
    support: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    cost_micros: int = 0

    def __post_init__(self) -> None:
        counts = (self.true_positive, self.false_positive, self.true_negative, self.false_negative)
        if self.generation < 0 or self.support <= 0 or any(v < 0 for v in counts):
            raise Refused("INVALID_CALIBRATION_COUNTS")
        if sum(counts) != self.support:
            raise Refused("SUPPORT_MISMATCH")
        if self.cost_micros < 0:
            raise Refused("NEGATIVE_COST")

    @property
    def precision(self) -> float:
        d = self.true_positive + self.false_positive
        return self.true_positive / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.true_positive + self.false_negative
        return self.true_positive / d if d else 0.0

    @property
    def false_equivalence_rate(self) -> float:
        d = self.false_positive + self.true_negative
        return self.false_positive / d if d else 0.0

    @property
    def false_refusal_rate(self) -> float:
        d = self.false_negative + self.true_positive
        return self.false_negative / d if d else 0.0
