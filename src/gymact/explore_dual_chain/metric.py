from dataclasses import dataclass
from fractions import Fraction
from .refusal import DualChainRefusal

@dataclass(frozen=True)
class CostMatrix:
    costs: tuple[tuple[str, str, Fraction], ...]

    def __post_init__(self) -> None:
        if any(c < 0 for _, _, c in self.costs):
            raise DualChainRefusal("NEGATIVE_COST")
        if len({(x, y) for x, y, _ in self.costs}) != len(self.costs):
            raise DualChainRefusal("DUPLICATE_COST")

    def get(self, x: str, y: str) -> Fraction:
        try:
            return {(a, b): c for a, b, c in self.costs}[(x, y)]
        except KeyError as exc:
            raise DualChainRefusal("MISSING_COST", f"{x}->{y}") from exc
