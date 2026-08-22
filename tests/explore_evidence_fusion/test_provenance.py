import unittest
from gymact.explore_evidence_fusion.provenance import ProvenanceGraph
class T(unittest.TestCase):
 def test_cycle_and_transitive_derivation(self):
  g=ProvenanceGraph((("a","b"),("b","c"))); self.assertTrue(g.derives("a","c"))
  with self.assertRaisesRegex(ValueError,"CYCLE"): ProvenanceGraph((("a","b"),("b","a")))
