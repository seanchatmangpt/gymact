import unittest
from datetime import UTC, datetime

from gymact.explore_evidence_calibration.contracts import Refusal, Subject
from gymact.explore_evidence_calibration.engine import qualify, require_do
from gymact.explore_evidence_calibration.estimate import estimate
from gymact.explore_evidence_calibration.receipt import replay
from gymact.explore_evidence_calibration.trials import CalibrationTrial
from gymact.explore_evidence_calibration.witness import CurrentWitness, EvidenceCluster


class E2ETests(unittest.TestCase):
    def test_under_calibrated_unknown_then_calibrated_bounded(self):
        now = datetime.now(UTC)
        subject = Subject("seanchatmangpt/gymact", "a" * 40)
        cluster = EvidenceCluster("c1", ("s1",))
        witness = CurrentWitness("e1", subject, "c1", "s1", "PASS", now)
        short_trials = tuple(
            CalibrationTrial("s1", str(index), True, True, now)
            for index in range(2)
        )
        short_estimate = estimate("s1", short_trials)
        q1 = qualify(
            subject,
            (cluster,),
            (witness,),
            (short_estimate,),
            now=now,
            dependency_edges={"root": ()},
            dependency_standings={},
            dependency_root="root",
        )
        self.assertEqual(q1.decision.standing, "UNKNOWN")
        outcomes = [True, True, True, False, True, True]
        full_trials = tuple(
            CalibrationTrial("s1", str(index), True, actual, now)
            for index, actual in enumerate(outcomes)
        )
        full_estimate = estimate("s1", full_trials)
        q2 = qualify(
            subject,
            (cluster,),
            (witness,),
            (full_estimate,),
            now=now,
            dependency_edges={"root": ()},
            dependency_standings={},
            dependency_root="root",
            transactional=True,
        )
        self.assertIn(q2.decision.standing, {"PARTIAL_ALIVE", "UNKNOWN"})
        self.assertTrue(replay(q2.receipt))
        self.assertFalse(q2.receipt.payload["actuation_performed"])
        with self.assertRaisesRegex(Refusal, "REFUSED_UNRECEIPTED_ACTUATION"):
            require_do()
