from datetime import datetime, timedelta, timezone
import unittest
from gymact.explore_cut_strategy.subject import Subject
from gymact.explore_cut_strategy.epoch import ProducerEpoch
from gymact.explore_cut_strategy.cut import EvidenceCut
from gymact.explore_cut_strategy.comparison import compare_strategies,pareto
NOW=datetime(2026,8,22,15,0,tzinfo=timezone.utc)
def e(g): return ProducerEpoch(Subject.parse("a/r@"+"a"*40),g,f"{g:064x}",NOW)
class T(unittest.TestCase):
    def test_comparison_and_pareto(self):
        c1=EvidenceCut("a",1,(e(1),),NOW,NOW+timedelta(hours=1)); c2=EvidenceCut("b",2,(e(2),),NOW,NOW+timedelta(hours=1)); cur={"a/r":e(2)}
        results=compare_strategies((c1,c2),cur)
        self.assertEqual(len(results),3)
        self.assertGreaterEqual(len(pareto(results)),1)
