from datetime import datetime, timedelta, timezone
import unittest
from gymact.explore_cut_strategy.subject import Subject
from gymact.explore_cut_strategy.epoch import ProducerEpoch
from gymact.explore_cut_strategy.cut import EvidenceCut
from gymact.explore_cut_strategy.strategies import CutStrategy,select_cut
NOW=datetime(2026,8,22,15,0,tzinfo=timezone.utc)
def e(repo,sha,g): return ProducerEpoch(Subject.parse(f"{repo}@{sha}"),g,f"{g:064x}",NOW)
class T(unittest.TestCase):
    def test_strategies_differ(self):
        a=EvidenceCut("latest",3,(e("a/r","a"*40,1),e("b/r","b"*40,1)),NOW,NOW+timedelta(hours=1))
        b=EvidenceCut("fresh",2,(e("a/r","a"*40,3),e("b/r","b"*40,3)),NOW,NOW+timedelta(hours=1)); cur={x.subject.repo:x for x in b.epochs}
        self.assertEqual(select_cut((a,b),cur,CutStrategy.LATEST_COMPLETE).cut_id,"latest")
        self.assertEqual(select_cut((a,b),cur,CutStrategy.MAX_FRESHNESS).cut_id,"fresh")
