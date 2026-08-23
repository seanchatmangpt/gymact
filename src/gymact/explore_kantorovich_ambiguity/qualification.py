from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .receipt import Receipt, issue

@dataclass(frozen=True)
class Qualification:
    standing: str
    receipt: Receipt | None
    reasons: tuple[str, ...]

def qualify(
    *,
    subject: str,
    worst_loss: Fraction,
    max_loss: Fraction,
    oracle_gap: Fraction,
    max_oracle_gap: Fraction,
    dependencies: tuple[str, ...],
) -> Qualification:
    broken = tuple(d for d in dependencies if d not in {"ALIVE", "PARTIAL_ALIVE"})
    if broken:
        return Qualification("BUILD_BROKEN", None, broken)
    if worst_loss > max_loss or oracle_gap > max_oracle_gap:
        return Qualification("UNSUPPORTED", None, ("BOUND_EXCEEDED",))
    receipt = issue(
        {
            "subject": subject,
            "standing": "PARTIAL_ALIVE",
            "worst_loss": str(worst_loss),
            "oracle_gap": str(oracle_gap),
            "authority": "VERIFY",
            "actuation_performed": False,
        }
    )
    return Qualification("PARTIAL_ALIVE", receipt, ())
