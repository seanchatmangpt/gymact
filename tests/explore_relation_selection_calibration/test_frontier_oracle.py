import pytest

from gymact.explore_relation_selection_calibration.calibration import CalibrationEvidence
from gymact.explore_relation_selection_calibration.errors import Refused
from gymact.explore_relation_selection_calibration.frontier import current_frontier
from gymact.explore_relation_selection_calibration.oracle import OracleWitness, require_independent
from gymact.explore_relation_selection_calibration.relation import Relation
from gymact.explore_relation_selection_calibration.subject import Subject

SUBJECT = Subject("seanchatmangpt/gymact", "5" * 40, "6" * 64)


def test_split_frontier_refuses() -> None:
    a = CalibrationEvidence(SUBJECT, Relation.EXACT, 2, 20, 10, 0, 10, 0)
    b = CalibrationEvidence(SUBJECT, Relation.EXACT, 2, 20, 9, 0, 11, 0)
    with pytest.raises(Refused, match="DIVERGENT_CALIBRATION_FRONTIER"):
        current_frontier((a, b))


def test_oracle_aliasing_refuses() -> None:
    with pytest.raises(Refused, match="ORACLE_ALIASING"):
        require_independent((OracleWitness("same", "same"), OracleWitness("same", "same")))
