from dataclasses import dataclass
from fractions import Fraction

from .evidence import LoggedOutcome


@dataclass(frozen=True)
class World:
    name: str
    rows: tuple[LoggedOutcome, ...]


def support_dropout() -> World:
    return World(
        "support_dropout",
        (LoggedOutcome("c", "a", Fraction(1), Fraction(1, 2), Fraction(0)),),
    )


def hidden_confounding() -> World:
    rows = (
        LoggedOutcome("high-risk", "treat", Fraction(1), Fraction(1, 4), Fraction(3, 4)),
        LoggedOutcome("low-risk", "control", Fraction(0), Fraction(3, 4), Fraction(1, 4)),
    )
    return World("hidden_confounding", tuple(sorted(rows)))
