from __future__ import annotations

from dataclasses import dataclass

from .admission import admit_observations
from .authority import require_explore_authority
from .observation import Observation
from .receipt import Receipt, make_receipt
from .standing import standing
from .subject import Subject
from .window import ObservationWindow


@dataclass(frozen=True, slots=True)
class Qualification:
    subject: Subject
    standing: str
    observations: tuple[Observation, ...]
    receipt: Receipt
    actuation_performed: bool = False


def qualify(
    subject: Subject,
    window: ObservationWindow,
    observations: tuple[Observation, ...],
) -> Qualification:
    require_explore_authority("VERIFY")
    admitted = admit_observations(subject, window, observations)
    bounded = standing(admitted)
    receipt = make_receipt(subject, bounded, admitted)
    return Qualification(subject, bounded, admitted, receipt, False)
