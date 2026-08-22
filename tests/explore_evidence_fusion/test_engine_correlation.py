import unittest
from datetime import datetime,timezone
from gymact.explore_evidence_fusion.subject import Subject
from gymact.explore_evidence_fusion.source import EvidenceSource
from gymact.explore_evidence_fusion.observation import Observation
from gymact.explore_evidence_fusion.provenance import ProvenanceGraph
from gymact.explore_evidence_fusion.engine import qualify
from gymact.explore_evidence_fusion.receipt import replay
N=datetime(2026,8,22,18,0,tzinfo=timezone.utc)
def o(i): return Observation(EvidenceSource("seanchatmangpt/gymact",f"r{i}",str(i)*64,"same"),"FOCUSED","PASS",N,f"e{i}")
class T(unittest.TestCase):
 def test_correlated_green_votes_do_not_manufacture_positive_standing(self):
  q=qualify(subject=Subject("seanchatmangpt/gymact@"+"a"*40),observations=[o(1),o(2),o(3)],graph=ProvenanceGraph(),now=N)
  self.assertEqual(q.standing,"UNKNOWN"); self.assertTrue(replay(q.receipt)); self.assertFalse(q.receipt.actuation_performed)
