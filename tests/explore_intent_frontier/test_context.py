import unittest
from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.subject import Subject
class TestContext(unittest.TestCase):
    def test_fingerprint_is_exact_and_generation_bounded(self):
        s=Subject("a/b","1"*40); c=SelectionContext(s,"cut-1","2"*64,3,"MIN_SKEW","3"*64)
        self.assertEqual(len(c.fingerprint),64)
        with self.assertRaisesRegex(ValueError,"REFUSED_INVALID_SELECTION_CONTEXT"):
            SelectionContext(s,"cut","2"*64,-1,"MIN_SKEW","3"*64)
if __name__=="__main__": unittest.main()
