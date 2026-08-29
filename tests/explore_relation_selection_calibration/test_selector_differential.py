from gymact.explore_relation_selection_calibration.calibration import CalibrationEvidence
from gymact.explore_relation_selection_calibration.meta_selector import compare
from gymact.explore_relation_selection_calibration.relation import Relation
from gymact.explore_relation_selection_calibration.subject import Subject

SUBJECT = Subject("seanchatmangpt/gymact", "3" * 40, "4" * 64)


def e(relation: Relation, tp: int, fp: int, tn: int, fn: int, cost: int) -> CalibrationEvidence:
    return CalibrationEvidence(SUBJECT, relation, 1, tp + fp + tn + fn, tp, fp, tn, fn, cost)


def test_selector_families_remain_observably_distinct() -> None:
    items = (
        e(Relation.EXACT, 28, 1, 10, 1, 900),
        e(Relation.STUTTER, 25, 0, 12, 3, 400),
        e(Relation.PARTIAL_ORDER, 26, 2, 10, 2, 300),
        e(Relation.ACTIVITY, 30, 3, 6, 1, 100),
    )
    bundle = compare(items)
    assert bundle.strongest == frozenset({Relation.EXACT})
    assert bundle.information
    assert bundle.pareto
    assert bundle.minimax
    assert tuple(bundle.information) != tuple(bundle.pareto)
