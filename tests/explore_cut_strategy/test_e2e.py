from datetime import datetime, timedelta, timezone
import unittest
from gymact.explore_cut_strategy.subject import Subject
from gymact.explore_cut_strategy.epoch import ProducerEpoch
from gymact.explore_cut_strategy.cut import EvidenceCut
from gymact.explore_cut_strategy.observation import Observation,Outcome
from gymact.explore_cut_strategy.engine import qualify
from gymact.explore_cut_strategy.strategies import CutStrategy
from gymact.explore_cut_strategy.failure import advance_one
NOW=datetime(2026,8,22,15,0,tzinfo=timezone.utc)
def e(g): return ProducerEpoch(Subject.parse("a/r@"+"a"*40),g,f"{g:064x}",NOW)
class T(unittest.TestCase):
    def test_current_cut_qualifies_then_stales(self):
        ep=e(2); cur={ep.subject.repo:ep}; cut=EvidenceCut("current",2,(ep,),NOW,NOW+timedelta(hours=1)); obs=(Observation(ep,"REPOSITORY",Outcome.PASS,"ev",NOW),)
        q=qualify(subject=ep.subject.key,cuts=(cut,),current=cur,observations=obs,now=NOW,strategy=CutStrategy.MAX_FRESHNESS)
        self.assertEqual(q.standing,"PARTIAL_ALIVE"); self.assertFalse(q.receipt.actuation_performed)
        with self.assertRaisesRegex(ValueError,"REFUSED_STALE_CUT_EPOCH"):
            qualify(subject=ep.subject.key,cuts=(cut,),current=advance_one(cur,0),observations=obs,now=NOW,strategy=CutStrategy.MAX_FRESHNESS)
