from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from enum import StrEnum

from .calibration import Calibration
from .receipt import Receipt, ReceiptBody
from .selectors import Candidate, Selector, select


class Standing(StrEnum):
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    UNSUPPORTED = "UNSUPPORTED"
    BUILD_BROKEN = "BUILD_BROKEN"


@dataclass(frozen=True, slots=True)
class Qualification:
    selected: Candidate
    standing: Standing
    receipt: Receipt | None


def qualify(
    subject: str,
    candidates: tuple[Candidate, ...],
    selector: Selector,
    calibration: Calibration,
    max_worst_risk: Fraction,
    dependency_broken: bool = False,
) -> Qualification:
    selected = select(candidates, selector)
    if dependency_broken:
        return Qualification(selected, Standing.BUILD_BROKEN, None)
    standing = Standing.PARTIAL_ALIVE
    if selected.worst_risk > max_worst_risk or calibration.miss_rate > Fraction(1, 10):
        standing = Standing.UNSUPPORTED
    receipt = Receipt.issue(ReceiptBody(subject, selector.value, standing.value))
    return Qualification(selected, standing, receipt)
