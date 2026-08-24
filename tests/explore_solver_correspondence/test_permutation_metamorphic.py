from gymact.explore_kantorovich_ambiguity.measure import FiniteMeasure
from gymact.explore_solver_correspondence.corpus import line_metric
from gymact.explore_solver_correspondence.metamorphic import require_cost_invariance
from gymact.explore_solver_correspondence.permutation import (
    permute_measure,
    permute_metric,
)
from gymact.explore_solver_correspondence.primal_adapter import run_primal
from gymact.explore_solver_correspondence.subject import SolverSubject


def test_label_permutation_preserves_transport_cost():
    subject = SolverSubject(
        "seanchatmangpt/gymact",
        "d51231730796ef512cc942462a789d69f009affd",
        "permutation",
    )
    a = FiniteMeasure.from_mapping({"a": 1, "b": 2, "c": 3})
    b = FiniteMeasure.from_mapping({"a": 3, "b": 2, "c": 1})
    metric = line_metric(("a", "b", "c"))
    mapping = {"a": "z", "b": "x", "c": "y"}
    baseline = run_primal(subject, a, b, metric)
    transformed = run_primal(
        subject,
        permute_measure(a, mapping),
        permute_measure(b, mapping),
        permute_metric(metric, mapping),
    )
    assert require_cost_invariance(baseline, transformed).cost_preserved
