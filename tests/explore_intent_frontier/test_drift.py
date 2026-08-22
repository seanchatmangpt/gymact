import unittest
from dataclasses import replace
from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.drift import DriftKind,classify
from gymact.explore_intent_frontier.subject import Subject
class TestDrift(unittest.TestCase):
    def test_typed_context_drift(self):
        c=SelectionContext(Subject("a/b","1"*40),"cut","2"*64,1,"LATEST_COMPLETE","3"*64)
        self.assertIs(classify(c,c).kind,DriftKind.UNCHANGED)
        self.assertIs(classify(c,replace(c,policy_digest="4"*64)).kind,DriftKind.POLICY)
        self.assertIs(classify(c,replace(c,policy_digest="4"*64,strategy="MIN_SKEW")).kind,DriftKind.MULTIPLE)
if __name__=="__main__": unittest.main()
