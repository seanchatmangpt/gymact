from gymact.explore_solver_correspondence.subject import SolverSubject
from gymact.explore_solver_correspondence.pipeline import verify_correspondence
from gymact.explore_solver_correspondence.receipt import replay
from gymact.explore_solver_correspondence.corpus import line_metric
from gymact.explore_kantorovich_ambiguity.measure import FiniteMeasure


def test_end_to_end_verification_is_non_actuating_and_replayable():
    subject = SolverSubject("seanchatmangpt/gymact", "d51231730796ef512cc942462a789d69f009affd", "solver-correspondence")
    a = FiniteMeasure.from_mapping({"a": 1, "b": 1})
    b = FiniteMeasure.from_mapping({"a": 0, "b": 1})
    metric = line_metric(("a", "b"))
    evidence, standing, receipt = verify_correspondence(subject, a, b, metric)
    assert evidence.cost_gap == 0
    assert standing.state == "ALIVE"
    assert receipt.authority == "VERIFY"
    assert receipt.actuation_performed is False
    assert replay(receipt, receipt.digest)
