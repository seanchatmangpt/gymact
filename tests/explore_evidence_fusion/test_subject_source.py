import unittest
from gymact.explore_evidence_fusion.subject import Subject
from gymact.explore_evidence_fusion.source import EvidenceSource
class T(unittest.TestCase):
 def test_exact_and_source(self):
  s=Subject("seanchatmangpt/gymact@"+"a"*40); self.assertEqual(s.repo,"seanchatmangpt/gymact")
  with self.assertRaisesRegex(ValueError,"INEXACT"): Subject("seanchatmangpt/gymact@abc")
  e=EvidenceSource("seanchatmangpt/gymact","r1","1"*64,"fam"); self.assertEqual(len(e.fingerprint),64)
