from .dual import DualPotential
from .feasibility import reduced_costs
from .metric import CostMatrix
from .primal import PrimalPlan
from .refusal import DualChainRefusal


def verify_complementarity(plan: PrimalPlan, dual: DualPotential, metric: CostMatrix) -> None:
    slack = reduced_costs(dual, metric)
    for x, y, amount in plan.flow:
        if amount > 0 and slack[(x, y)] != 0:
            raise DualChainRefusal("COMPLEMENTARITY_VIOLATION", f"{x}->{y}")
