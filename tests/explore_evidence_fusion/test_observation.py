import unittest
from datetime import datetime, timezone
from gymact.explore_evidence_fusion.source import EvidenceSource
from gymact.explore_evidence_fusion.observation import Observation
class T(unittest.TestCase):
 def test_observation_time_and_vocab(self):
  s=EvidenceSource("seanchatmangpt/gymact","r1","1"*64,"fam")
  o=Observation(s,"FOCUSED","PASS",datetime.now(timezone.utc),"e1"); self.assertEqual(o.outcome,"PASS")
  with self.assertRaisesRegex(ValueError,"NAIVE"): Observation(s,"FOCUSED","PASS",datetime(2026,1,1),"e2")
