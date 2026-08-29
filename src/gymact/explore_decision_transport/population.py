from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused


@dataclass(frozen=True, slots=True)
class Population:
    masses: dict[str, Fraction]

    @classmethod
    def normalized(cls, masses: dict[str, Fraction]) -> "Population":
        if not masses or any(v < 0 for v in masses.values()):
            raise Refused("INVALID_POPULATION")
        total = sum(masses.values(), Fraction())
        if total <= 0:
            raise Refused("EMPTY_POPULATION")
        return cls({k: v / total for k, v in sorted(masses.items()) if v > 0})
