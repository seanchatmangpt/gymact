from dataclasses import dataclass
from fractions import Fraction
from .refusal import DualChainRefusal

@dataclass(frozen=True)
class PrimalPlan:
    flow: tuple[tuple[str, str, Fraction], ...]
    cost: Fraction

    def __post_init__(self) -> None:
        if self.cost < 0 or any(v < 0 for _, _, v in self.flow):
            raise DualChainRefusal("INVALID_PRIMAL_PLAN")

    @property
    def positive_support(self) -> tuple[tuple[str, str], ...]:
        return tuple((x, y) for x, y, v in self.flow if v > 0)
