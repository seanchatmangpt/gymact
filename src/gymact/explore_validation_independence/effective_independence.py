from dataclasses import dataclass
from fractions import Fraction

from .overlap import Overlap
from .refusal import Refused
from .validator import ValidatorWitness


@dataclass(frozen=True)
class IndependenceScore:
    overlap: Fraction
    effective: Fraction


def effective_independence(
    left: ValidatorWitness, right: ValidatorWitness, overlap: Overlap
) -> IndependenceScore:
    left.require_independent(right)
    if overlap.ratio == 1:
        raise Refused("FULL_ANCESTRY_ALIAS")
    return IndependenceScore(overlap.ratio, Fraction(1) - overlap.ratio)
