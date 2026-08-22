import unittest
from datetime import datetime,timezone
from gymact.explore_evidence_fusion.subject import Subject
from gymact.explore_evidence_fusion.source import EvidenceSource
from gymact.explore_evidence_fusion.observation import Observation
from gymact.explore_evidence_fusion.provenance import ProvenanceGraph
from gymact.explore_evidence_fusion.engine import qualify
N=datetime(2026,8,22,18,0,tzinfo=timezone.utc)
def o(i,fam): return Observation(EvidenceSource("seanchatmangpt/gymact",f"r{i}",str(i)*64,fam),"FOCUSED","PASS",N,f"e{i}")
class T(unittest.TestCase):
 def test_independent_clusters_qualify_bounded_and_do_refuses(self):
  s=Subject("seanchatmangpt/gymact@"+"a"*40); a,b=o(1,"fam1"),o(2,"fam2"); pairs={frozenset(("e1","e2"))}
  q=qualify(subject=s,observations=[a,b],graph=ProvenanceGraph(),now=N,independent_pairs=pairs,transactional=True)
  self.assertEqual(q.standing,"PARTIAL_ALIVE"); self.assertEqual(q.receipt.store,"SQLITE")
  with self.assertRaisesRegex(PermissionError,"UNRECEIPTED"): qualify(subject=s,observations=[a,b],graph=ProvenanceGraph(),now=N,independent_pairs=pairs,requested_action="DO")
