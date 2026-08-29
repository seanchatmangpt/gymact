from fractions import Fraction
from .dual import DualPotential
from .metric import CostMatrix
from .refusal import DualChainRefusal

def reduced_costs(dual: DualPotential, metric: CostMatrix) -> dict[tuple[str, str], Fraction]:
    left, right = dict(dual.left), dict(dual.right)
    out = {}
    for x, y, cost in metric.costs:
        if x not in left or y not in right:
            raise DualChainRefusal("DUAL_SUPPORT_MISMATCH")
        out[(x, y)] = cost - left[x] - right[y]
    return out

def verify_dual_feasible(dual: DualPotential, metric: CostMatrix) -> None:
    if any(v < 0 for v in reduced_costs(dual, metric).values()):
        raise DualChainRefusal("DUAL_INFEASIBLE")
