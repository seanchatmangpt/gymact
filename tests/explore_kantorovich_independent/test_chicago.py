from fractions import Fraction
from pathlib import Path

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_independent.differential import compare
from gymact.explore_kantorovich_independent.identity import VerificationSubject
from gymact.explore_kantorovich_independent.primal_to_dual import construct_dual
from gymact.explore_kantorovich_independent.raw_verifier import verify
from gymact.explore_kantorovich_independent.receipt import issue_receipt, replay


def test_end_to_end_independent_certificate_and_replay_preserve_engine_separation() -> None:
    points = {"a": 0, "b": 10, "c": 1, "d": 11}
    metric = GroundMetric.admit(set(points), {(x, y): abs(points[x] - points[y]) for x in points for y in points})
    source = FiniteMeasure.normalize({"a": 1, "b": 1})
    target = FiniteMeasure.normalize({"c": 1, "d": 1})
    plan = TransportPlan({("a", "c"): Fraction(1, 2), ("b", "d"): Fraction(1, 2)})
    potential = construct_dual(plan, source, target, metric)
    witness = verify(plan, potential, source, target, metric)
    comparison = compare(plan, potential, source, target, metric)
    subject = VerificationSubject.admit("seanchatmangpt/gymact", "5" * 40, "kantorovich-duality/v1")
    receipt = issue_receipt(subject, witness)
    assert comparison.manufacturer_primal == comparison.independent_primal == Fraction(1)
    assert replay(receipt)
    assert receipt.authority == "VERIFY" and not receipt.actuation_performed


def test_independent_equation_engine_has_no_certificate_or_checker_dependency() -> None:
    root = Path(__file__).parents[2] / "src" / "gymact" / "explore_kantorovich_independent"
    engine_files = ["raw_marginals.py", "raw_primal.py", "raw_dual.py", "raw_feasibility.py", "raw_reduced_cost.py", "raw_complementarity.py", "raw_verifier.py"]
    forbidden = ("explore_kantorovich_duality.certificate", "explore_kantorovich_duality.checker", "from .certificate", "from .checker")
    for name in engine_files:
        text = (root / name).read_text()
        assert not any(token in text for token in forbidden), name
