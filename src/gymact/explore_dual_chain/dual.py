from dataclasses import dataclass
from fractions import Fraction
from .refusal import DualChainRefusal

@dataclass(frozen=True)
class DualPotential:
    left: tuple[tuple[str, Fraction], ...]
    right: tuple[tuple[str, Fraction], ...]

    def __post_init__(self) -> None:
        if len(dict(self.left)) != len(self.left) or len(dict(self.right)) != len(self.right):
            raise DualChainRefusal("DUPLICATE_DUAL_LABEL")

    def value(self, mu: dict[str, Fraction], nu: dict[str, Fraction]) -> Fraction:
        return sum((mu[x] * v for x, v in self.left), Fraction()) + sum((nu[y] * v for y, v in self.right), Fraction())
