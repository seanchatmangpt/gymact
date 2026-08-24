from fractions import Fraction

from gymact.explore_kantorovich_ambiguity.measure import FiniteMeasure
from gymact.explore_solver_correspondence.corpus import line_metric
from gymact.explore_solver_correspondence.correspondence import compare
from gymact.explore_solver_correspondence.oracle_adapter import run_oracle
from gymact.explore_solver_correspondence.primal_adapter import run_primal
from gymact.explore_solver_correspondence.subject import SolverSubject


def test_direct_predecessor_engines_share_exact_optimum():
    subject = SolverSubject(
        "seanchatmangpt/gymact",
        "d51231730796ef512cc942462a789d69f009affd",
        "finite-w1",
    )
    a = FiniteMeasure.from_mapping({"a": 1, "b": 2, "c": 1})
    b = FiniteMeasure.from_mapping({"a": 2, "b": 1, "c": 1})
    metric = line_metric(("a", "b", "c"))
    evidence = compare(
        run_primal(subject, a, b, metric),
        run_oracle(subject, a, b, metric),
    )
    assert evidence.cost_gap == Fraction(0)
    assert evidence.primal_engine != evidence.oracle_engine
