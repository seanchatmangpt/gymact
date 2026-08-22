from datetime import datetime, timedelta, timezone
import unittest
from gymact.explore_cut_strategy.subject import Subject
from gymact.explore_cut_strategy.epoch import ProducerEpoch
from gymact.explore_cut_strategy.cut import EvidenceCut
from gymact.explore_cut_strategy.observation import Observation,Outcome
from gymact.explore_cut_strategy.admission import admit_cut
NOW=datetime(2026,8,22,15,0,tzinfo=timezone.utc)
def epoch(g): return ProducerEpoch(Subject.parse("a/r@"+"a"*40),g,f"{g:064x}",NOW)
class T(unittest.TestCase):
    def test_stale_cut_refuses(self):
        old,new=epoch(1),epoch(2); cut=EvidenceCut("c",1,(old,),NOW,NOW+timedelta(hours=1)); obs=(Observation(old,"REPOSITORY",Outcome.PASS,"e",NOW),)
        with self.assertRaisesRegex(ValueError,"REFUSED_STALE_CUT_EPOCH"):
            admit_cut(cut,{old.subject.repo:new},obs,NOW)
