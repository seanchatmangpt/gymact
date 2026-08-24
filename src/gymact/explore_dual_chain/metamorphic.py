from .primal import PrimalPlan
from .dual import DualPotential

def rename_plan(plan: PrimalPlan, mapping: dict[str, str]) -> PrimalPlan:
    return PrimalPlan(tuple((mapping.get(x, x), mapping.get(y, y), v) for x, y, v in plan.flow), plan.cost)

def rename_dual(dual: DualPotential, mapping: dict[str, str]) -> DualPotential:
    return DualPotential(tuple((mapping.get(x, x), v) for x, v in dual.left), tuple((mapping.get(y, y), v) for y, v in dual.right))
