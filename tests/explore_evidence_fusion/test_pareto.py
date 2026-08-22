import unittest
from gymact.explore_evidence_fusion.strategies import Decision,Strategy
from gymact.explore_evidence_fusion.pareto import pareto_frontier
class T(unittest.TestCase):
 def test_dominated_strategy_removed(self):
  a=Decision(Strategy.CLUSTER_MAJORITY,"UNKNOWN",(1,0,0),"a")
  b=Decision(Strategy.MINIMAX_FAILURE,"UNKNOWN",(2,0,0),"b")
  self.assertEqual(pareto_frontier((a,b)),(b,))
