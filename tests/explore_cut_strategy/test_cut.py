from datetime import datetime, timedelta, timezone
import unittest
from gymact.explore_cut_strategy.subject import Subject
from gymact.explore_cut_strategy.epoch import ProducerEpoch
from gymact.explore_cut_strategy.cut import EvidenceCut
NOW=datetime(2026,8,22,15,0,tzinfo=timezone.utc)
def epoch(sha="a"*40): return ProducerEpoch(Subject.parse(f"a/r@{sha}"),1,"1".zfill(64),NOW)
class T(unittest.TestCase):
    def test_duplicate_and_lease(self):
        c=EvidenceCut("c",1,(epoch(),),NOW,NOW+timedelta(hours=1)); self.assertTrue(c.is_active(NOW))
        with self.assertRaisesRegex(ValueError,"REFUSED_DUPLICATE_PRODUCER"):
            EvidenceCut("x",1,(epoch(),epoch("b"*40)),NOW,NOW+timedelta(hours=1))
