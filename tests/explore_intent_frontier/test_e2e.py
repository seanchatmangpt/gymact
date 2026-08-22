import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from gymact.explore_intent_frontier.compatibility import CompatibilityKind, CompatibilityWitness
from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.engine import ActionClass, qualify, require
from gymact.explore_intent_frontier.intent import SelectionIntent
from gymact.explore_intent_frontier.receipt import replay
from gymact.explore_intent_frontier.storage import StoreKind
from gymact.explore_intent_frontier.strategies import FreshnessStrategy
from gymact.explore_intent_frontier.subject import Subject


class TestE2E(unittest.TestCase):
    def test_policy_drift_requalifies_without_do(self):
        t = datetime(2026, 8, 22, 16, tzinfo=UTC)
        before = SelectionContext(
            Subject("seanchatmangpt/gymact", "7" * 40), "cut", "2" * 64, 7, "MIN_SKEW", "3" * 64
        )
        after = replace(before, policy_digest="4" * 64)
        intent = SelectionIntent(before, "intent-0001", t, t + timedelta(hours=1))
        w = CompatibilityWitness(
            before.fingerprint,
            after.fingerprint,
            CompatibilityKind.BACKWARD_COMPATIBLE,
            "policy-proof",
        )
        q = qualify(
            intents=(intent,),
            before=before,
            after=after,
            strategy=FreshnessStrategy.REQUALIFY_COMPATIBLE,
            now=t,
            witness=w,
            durable=True,
            transactional=True,
        )
        self.assertEqual(q.decision.standing, "REQUALIFYING")
        self.assertIs(q.store.kind, StoreKind.SQLITE)
        self.assertTrue(replay(q.receipt))
        self.assertFalse(q.receipt.body["actuation_performed"])
        with self.assertRaisesRegex(PermissionError, "REFUSED_UNRECEIPTED_ACTUATION"):
            require(ActionClass.DO)


if __name__ == "__main__":
    unittest.main()
