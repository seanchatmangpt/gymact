import pytest
from fractions import Fraction
from gymact.explore_dual_chain.authority import Action, admit_action
from gymact.explore_dual_chain.dual import DualPotential
from gymact.explore_dual_chain.metric import CostMatrix
from gymact.explore_dual_chain.feasibility import verify_dual_feasible
from gymact.explore_dual_chain.refusal import DualChainRefusal

def test_infeasible_dual_refuses():
    with pytest.raises(DualChainRefusal, match="DUAL_INFEASIBLE"):
        verify_dual_feasible(DualPotential((("a", Fraction(2)),), (("b", Fraction(1)),)), CostMatrix((("a", "b", Fraction(2)),)))

def test_ambient_do_refuses():
    with pytest.raises(DualChainRefusal, match="UNRECEIPTED_ACTUATION"):
        admit_action(Action.DO)
