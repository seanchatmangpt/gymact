import unittest
from gymact.explore_methodology_correspondence.closure import Closure
from gymact.explore_methodology_correspondence.receipt import Receipt
from gymact.explore_methodology_correspondence.replay import replay
from gymact.explore_methodology_correspondence.qualification import qualify

class TestReceiptQualification(unittest.TestCase):
    def test_receipted_closure(self):
        c=Closure(frozenset({'discovery','conformance'}),frozenset({'discovery','conformance'}))
        r=Receipt('o/r@'+'a'*40,'DISCOVERY','BEAM','PARTIAL_ALIVE')
        d=r.digest()
        self.assertTrue(replay(r,d))
        self.assertEqual(qualify(c,True).standing,'PARTIAL_ALIVE')
        self.assertFalse(replay(r,'0'*64))
