import unittest
from fractions import Fraction
from gymact.explore_calibration_regime.model import CalibrationModel
from gymact.explore_calibration_regime.drift import compare,classify
class T(unittest.TestCase):
 def test_drift(self):
  a=CalibrationModel("s",8,Fraction(9,10),Fraction(1,10),Fraction(1,10))
  b=CalibrationModel("s",8,Fraction(1,2),Fraction(1,2),Fraction(1,2))
  self.assertEqual(classify(compare(a,b)),"DRIFT")
