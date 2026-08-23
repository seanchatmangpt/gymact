import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_rail_consensus.clusters import correlated_clusters
from gymact.explore_rail_consensus.consensus import ConsensusStrategy
from gymact.explore_rail_consensus.metrics import measure
from gymact.explore_rail_consensus.observation import Outcome, RailObservation
from gymact.explore_rail_consensus.pareto import StrategyVector, pareto_frontier
from gymact.explore_rail_consensus.rail import VerificationRail
from gymact.explore_rail_consensus.subject import Subject

class MetricsParetoTest(unittest.TestCase):
    def test_exact_diversity_and_dominance(self):
        subject = Subject("o/r", "f" * 40)
        now = datetime.now(timezone.utc)
        observations = tuple(
            RailObservation(
                VerificationRail(subject, str(i), "same" if i < 2 else "other", str(i), "py", str(i)),
                str(i), Outcome.PASS, now,
            )
            for i in range(3)
        )
        self.assertEqual(measure(correlated_clusters(observations)).effective_diversity, Fraction(9, 5))
        dominated = StrategyVector(ConsensusStrategy.ALL_INDEPENDENT, 3, 3, 1)
        winner = StrategyVector(ConsensusStrategy.MINIMAX_FAILURE, 3, 2, 2)
        self.assertEqual(pareto_frontier((dominated, winner)), (winner,))
