import unittest
from dataclasses import replace
from gymact.explore_intent_frontier.compatibility import CompatibilityKind,CompatibilityWitness,admit_witness
from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.subject import Subject
class TestCompatibility(unittest.TestCase):
    def test_backward_compatibility_requires_stable_cut_and_strategy(self):
        a=SelectionContext(Subject("a/b","1"*40),"cut","2"*64,1,"MIN_SKEW","3"*64); b=replace(a,policy_digest="4"*64)
        w=CompatibilityWitness(a.fingerprint,b.fingerprint,CompatibilityKind.BACKWARD_COMPATIBLE,"policy-proof-1")
        admit_witness(a,b,w)
        c=replace(b,strategy="LATEST_COMPLETE")
        bad=CompatibilityWitness(a.fingerprint,c.fingerprint,CompatibilityKind.BACKWARD_COMPATIBLE,"bad-proof")
        with self.assertRaisesRegex(ValueError,"REFUSED_UNPROVEN_BACKWARD_COMPATIBILITY"): admit_witness(a,c,bad)
if __name__=="__main__": unittest.main()
