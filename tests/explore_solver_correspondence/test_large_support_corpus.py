from fractions import Fraction
from gymact.explore_solver_correspondence.subject import SolverSubject
from gymact.explore_solver_correspondence.primal_adapter import run_primal
from gymact.explore_solver_correspondence.oracle_adapter import run_oracle
from gymact.explore_solver_correspondence.correspondence import compare
from gymact.explore_solver_correspondence.corpus import corpus


def test_supports_two_through_four_have_zero_optimal_value_gap():
    subject = SolverSubject("seanchatmangpt/gymact", "d51231730796ef512cc942462a789d69f009affd", "finite-w1-corpus")
    seen = 0
    for a, b, metric in corpus(4):
        evidence = compare(run_primal(subject, a, b, metric), run_oracle(subject, a, b, metric))
        assert evidence.cost_gap == Fraction(0)
        seen += 1
    assert seen == 3
