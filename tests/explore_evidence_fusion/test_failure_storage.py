import unittest
from datetime import datetime,timezone
from gymact.explore_evidence_fusion.source import EvidenceSource
from gymact.explore_evidence_fusion.observation import Observation
from gymact.explore_evidence_fusion.failure import inject_family_correlation
from gymact.explore_evidence_fusion.storage import discover,select
N=datetime.now(timezone.utc)
def o(i,fam): return Observation(EvidenceSource("seanchatmangpt/gymact",f"r{i}",str(i)*64,fam),"FOCUSED","PASS",N,f"e{i}")
class T(unittest.TestCase):
 def test_deterministic_failure_and_storage_reversibility(self):
  xs=[o(1,"a"),o(2,"b")]
  self.assertEqual(inject_family_correlation(xs,7,.5),inject_family_correlation(xs,7,.5))
  self.assertEqual({s.name for s in discover()},{"MEMORY","JSONL","SQLITE"})
  self.assertEqual(select(transactional=True).name,"SQLITE")
