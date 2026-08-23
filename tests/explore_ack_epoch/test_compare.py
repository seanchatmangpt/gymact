import unittest
from gymact.explore_ack_epoch.strategy import Strategy
from gymact.explore_ack_epoch.compare import compare,pareto_completion
class T(unittest.TestCase):
 def test_compare(self):
  r=compare((Strategy("ALL"),Strategy("QUORUM")),{"a":"DISCHARGED","b":"DISCHARGED","c":"PENDING"})
  self.assertEqual(r,{"ALL":False,"QUORUM":True}); self.assertEqual(pareto_completion(r),("QUORUM",))
