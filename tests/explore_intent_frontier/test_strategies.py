import unittest
from dataclasses import replace
from gymact.explore_intent_frontier.compatibility import CompatibilityKind,CompatibilityWitness
from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.strategies import FreshnessStrategy,decide
from gymact.explore_intent_frontier.subject import Subject
class TestStrategies(unittest.TestCase):
    def test_three_strategies_remain_distinct(self):
        a=SelectionContext(Subject("a/b","1"*40),"cut","2"*64,1,"MIN_SKEW","3"*64); b=replace(a,policy_digest="4"*64)
        w=CompatibilityWitness(a.fingerprint,b.fingerprint,CompatibilityKind.BACKWARD_COMPATIBLE,"policy-proof")
        self.assertEqual(decide(FreshnessStrategy.RESELECT,a,b).standing,"REQUALIFYING")
        self.assertEqual(decide(FreshnessStrategy.REBIND_EQUIVALENT,a,b,w).standing,"REQUALIFYING")
        self.assertEqual(decide(FreshnessStrategy.REQUALIFY_COMPATIBLE,a,b,w).standing,"REQUALIFYING")
        self.assertEqual(decide(FreshnessStrategy.REBIND_EQUIVALENT,a,b,None).standing,"UNKNOWN")
if __name__=="__main__": unittest.main()
