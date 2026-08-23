from datetime import datetime, timezone
import unittest
from gymact.explore_cut_strategy.subject import Subject
from gymact.explore_cut_strategy.epoch import ProducerEpoch
from gymact.explore_cut_strategy.failure import advance_one
NOW=datetime(2026,8,22,15,0,tzinfo=timezone.utc)
def e(repo,sha): return ProducerEpoch(Subject.parse(f"{repo}@{sha}"),1,"1".zfill(64),NOW)
class T(unittest.TestCase):
    def test_seeded_advance(self):
        current={"a/r":e("a/r","a"*40),"b/r":e("b/r","b"*40)}
        self.assertEqual(advance_one(current,7),advance_one(current,7))
        self.assertEqual(sum(x.generation for x in advance_one(current,7).values()),3)
