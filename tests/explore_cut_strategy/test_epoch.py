from datetime import datetime, timezone
import unittest
from gymact.explore_cut_strategy.subject import Subject
from gymact.explore_cut_strategy.epoch import ProducerEpoch
NOW=datetime(2026,8,22,15,0,tzinfo=timezone.utc)
def epoch(generation=1): return ProducerEpoch(Subject.parse("a/r@"+"a"*40),generation,f"{generation:064x}",NOW)
class T(unittest.TestCase):
    def test_generation_and_time(self):
        self.assertTrue(epoch(2).newer_than(epoch(1)))
        with self.assertRaisesRegex(ValueError,"REFUSED_INVALID_GENERATION"):
            epoch(-1)
