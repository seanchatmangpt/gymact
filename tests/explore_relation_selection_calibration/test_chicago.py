from gymact.explore_relation_selection_calibration.admission import AdmissionPolicy
from gymact.explore_relation_selection_calibration.calibration import CalibrationEvidence
from gymact.explore_relation_selection_calibration.metamorphic import MetamorphicWitness
from gymact.explore_relation_selection_calibration.oracle import OracleWitness
from gymact.explore_relation_selection_calibration.qualify import qualify
from gymact.explore_relation_selection_calibration.relation import Relation
from gymact.explore_relation_selection_calibration.replay import replay
from gymact.explore_relation_selection_calibration.standing import Standing
from gymact.explore_relation_selection_calibration.subject import Subject

SUBJECT = Subject("seanchatmangpt/gymact", "8" * 40, "9" * 64)


def sample(relation: Relation, cost: int) -> CalibrationEvidence:
    return CalibrationEvidence(SUBJECT, relation, 7, 40, 20, 0, 20, 0, cost)


def test_chicago_calibrated_selection_is_bounded_and_replayable() -> None:
    evidence = tuple(sample(r, cost) for r, cost in zip(Relation, (400, 300, 100, 200)))
    witnesses = {r: MetamorphicWitness(r, True, True) for r in Relation}
    oracles = (OracleWitness("impl-a", "model-a"), OracleWitness("impl-b", "model-b"))
    result = qualify(evidence, witnesses, oracles, AdmissionPolicy(), hard_failure=False)
    assert result.standing is Standing.PARTIAL_ALIVE
    assert result.bundle is not None
    assert result.bundle.strongest == frozenset({Relation.EXACT})
    assert result.receipt is not None
    assert replay(result.receipt, result.receipt.digest()) == "REPLAY_MATCH"
    broken = qualify(evidence, witnesses, oracles, AdmissionPolicy(), hard_failure=True)
    assert broken.standing is Standing.BUILD_BROKEN
    assert broken.receipt is None
