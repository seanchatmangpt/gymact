import unittest

from gymact.explore_replicated_projection_quorum.engine import qualify
from gymact.explore_replicated_projection_quorum.failure import FailureKind, inject_failure
from gymact.explore_replicated_projection_quorum.receipt import ActionClass, replay
from gymact.explore_replicated_projection_quorum.selectors import SelectorKind
from world import NOW, SEMANTIC, SUBJECT, UNIVERSE, WINDOW, projection

class ChicagoCourt(unittest.TestCase):
    def test_healthy_quorum_visibility_loss_and_no_do(self):
        observations = tuple(projection(r) for r in ("r1", "r2", "r3"))
        healthy = qualify(observations, subject=SUBJECT, semantic_digest=SEMANTIC, universe=UNIVERSE, window=WINDOW, now=NOW, selector=SelectorKind.STRICT_MAJORITY_CURRENTNESS, transactional=True)
        self.assertEqual(healthy.assessment.standing, "PARTIAL_ALIVE")
        self.assertTrue(replay(healthy.receipt))
        degraded = qualify(inject_failure(observations, FailureKind.OMISSION, 9), subject=SUBJECT, semantic_digest=SEMANTIC, universe=UNIVERSE, window=WINDOW, now=NOW, selector=SelectorKind.STRICT_MAJORITY_CURRENTNESS)
        self.assertEqual(degraded.assessment.standing, "UNKNOWN")
        self.assertFalse(healthy.receipt.body["actuation_performed"])
        with self.assertRaises(Exception):
            qualify(observations, subject=SUBJECT, semantic_digest=SEMANTIC, universe=UNIVERSE, window=WINDOW, now=NOW, selector=SelectorKind.STRICT_MAJORITY_CURRENTNESS, action=ActionClass.DO)

if __name__ == "__main__":
    unittest.main()
