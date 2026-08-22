import unittest
from datetime import UTC,datetime,timedelta
from gymact.explore_calibration_regime.trials import Trial,admit_trials
from gymact.explore_calibration_regime.refusal import Refusal
class T(unittest.TestCase):
 def test_duplicate_future(self):
  now=datetime.now(UTC); t=Trial("s","1",True,True,now)
  with self.assertRaises(Refusal): admit_trials([t,t],now=now)
  with self.assertRaises(Refusal): admit_trials([Trial("s","2",True,True,now+timedelta(seconds=1))],now=now)
