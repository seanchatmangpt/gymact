from fractions import Fraction
from gymact.explore_dual_chain.primal import PrimalPlan
from gymact.explore_dual_chain.dual import DualPotential
from gymact.explore_dual_chain.metric import CostMatrix
from gymact.explore_dual_chain.feasibility import verify_dual_feasible
from gymact.explore_dual_chain.complementarity import verify_complementarity
from gymact.explore_dual_chain.strong_duality import verify_strong_duality

def test_exact_chain():
    plan = PrimalPlan((("a", "b", Fraction(1)),), Fraction(2))
    dual = DualPotential((("a", Fraction(1)),), (("b", Fraction(1)),))
    metric = CostMatrix((("a", "b", Fraction(2)),))
    verify_dual_feasible(dual, metric)
    verify_complementarity(plan, dual, metric)
    assert verify_strong_duality(plan, dual, {"a": Fraction(1)}, {"b": Fraction(1)}) == 0
