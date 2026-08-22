import unittest
from datetime import datetime,timezone
from gymact.explore_evidence_fusion.source import EvidenceSource
from gymact.explore_evidence_fusion.observation import Observation
from gymact.explore_evidence_fusion.provenance import ProvenanceGraph
from gymact.explore_evidence_fusion.clusters import correlated_clusters
N=datetime.now(timezone.utc)
def o(i,run,fam): return Observation(EvidenceSource("seanchatmangpt/gymact",run,str(i)*64,fam),"FOCUSED","PASS",N,f"e{i}")
class T(unittest.TestCase):
 def test_family_collapse_with_explicit_independence(self):
  xs=[o(1,"r1","same"),o(2,"r2","same"),o(3,"r3","other")]
  p={frozenset(("e1","e3")),frozenset(("e2","e3"))}
  self.assertEqual(sorted(map(len,correlated_clusters(xs,ProvenanceGraph(),p))),[1,2])
