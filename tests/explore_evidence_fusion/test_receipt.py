import unittest
from dataclasses import replace
from fractions import Fraction
from gymact.explore_evidence_fusion.subject import Subject
from gymact.explore_evidence_fusion.strategies import Strategy
from gymact.explore_evidence_fusion.storage import select
from gymact.explore_evidence_fusion.receipt import issue,replay
class T(unittest.TestCase):
 def test_tamper_and_actuation_bit_fail_replay(self):
  s=Subject("seanchatmangpt/gymact@"+"a"*40)
  r=issue(s,Strategy.MINIMAX_FAILURE,"UNKNOWN",1,Fraction(1,1),select())
  self.assertTrue(replay(r)); self.assertFalse(replay(replace(r,standing="ALIVE"))); self.assertFalse(replay(replace(r,actuation_performed=True)))
