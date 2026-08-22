import unittest
from datetime import UTC,datetime,timedelta
from gymact.explore_calibration_regime.trials import Trial
from gymact.explore_calibration_regime.window import CalibrationWindow
from gymact.explore_calibration_regime.model import fit
class T(unittest.TestCase):
 def test_fit(self):
  now=datetime.now(UTC); w=CalibrationWindow(now,now+timedelta(minutes=1))
  ts=[Trial("s",str(i),i%2==0,i%2==0,now+timedelta(seconds=i)) for i in range(4)]
  m=fit("s",ts,w); self.assertEqual(m.support,4); self.assertEqual(m.brier,0)
