from fractions import Fraction
from .primal import PrimalPlan
from .dual import DualPotential
from .refusal import DualChainRefusal

def verify_strong_duality(plan: PrimalPlan, dual: DualPotential, mu: dict[str, Fraction], nu: dict[str, Fraction]) -> Fraction:
    gap = plan.cost - dual.value(mu, nu)
    if gap != 0:
        raise DualChainRefusal("STRONG_DUALITY_GAP", str(gap))
    return gap
