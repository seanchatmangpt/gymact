import unittest
from datetime import datetime,timedelta,timezone
from gymact.explore_evidence_calibration.contracts import Refusal
from gymact.explore_evidence_calibration.trials import CalibrationTrial,admit_trials
class TrialTests(unittest.TestCase):
    def test_duplicate_and_future_trials_refuse(self):
        now=datetime.now(timezone.utc); trial=CalibrationTrial("s1","t1",True,True,now)
        with self.assertRaisesRegex(Refusal,"DUPLICATE"): admit_trials([trial,trial],now=now)
        future=CalibrationTrial("s1","t2",True,True,now+timedelta(seconds=1))
        with self.assertRaisesRegex(Refusal,"FUTURE"): admit_trials([future],now=now)
