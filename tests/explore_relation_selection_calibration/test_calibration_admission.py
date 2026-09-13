import pytest

from gymact.explore_relation_selection_calibration.admission import AdmissionPolicy, admit
from gymact.explore_relation_selection_calibration.calibration import CalibrationEvidence
from gymact.explore_relation_selection_calibration.errors import Refused
from gymact.explore_relation_selection_calibration.metamorphic import MetamorphicWitness
from gymact.explore_relation_selection_calibration.relation import Relation
from gymact.explore_relation_selection_calibration.subject import Subject

SUBJECT = Subject("seanchatmangpt/gymact", "1" * 40, "2" * 64)


def evidence(support: int, fp: int = 0) -> CalibrationEvidence:
    tn = max(0, support // 2 - fp)
    tp = support - tn - fp
    return CalibrationEvidence(SUBJECT, Relation.EXACT, 1, support, tp, fp, tn, 0)


def test_sparse_refuses() -> None:
    with pytest.raises(Refused, match="INSUFFICIENT_CALIBRATION_SUPPORT"):
        admit(
            evidence(10),
            MetamorphicWitness(Relation.EXACT, True, True),
            AdmissionPolicy(min_support=20),
        )


def test_false_equivalence_refuses() -> None:
    with pytest.raises(Refused, match="FALSE_EQUIVALENCE_BOUND_EXCEEDED"):
        admit(
            evidence(40, fp=8),
            MetamorphicWitness(Relation.EXACT, True, True),
            AdmissionPolicy(max_false_equivalence_upper=0.25),
        )
