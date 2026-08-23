from __future__ import annotations

from dataclasses import dataclass

from .census import Census, census
from .obligation import Obligation
from .receipt import Receipt
from .standing import Standing, standing
from .identity import Subject


@dataclass(frozen=True, slots=True)
class Qualification:
    census: Census
    standing: Standing
    receipt: Receipt


def qualify(subject: Subject, obligations: list[Obligation], *, blocked: bool = False) -> Qualification:
    c = census(obligations)
    s = standing([item.state for item in obligations], blocked=blocked)
    r = Receipt(subject, s, tuple(item.key for item in obligations))
    return Qualification(c, s, r)
