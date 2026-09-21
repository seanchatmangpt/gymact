from __future__ import annotations

import unittest
from fractions import Fraction

from gymact.explore_sequential_acquisition.budget import Budget
from gymact.explore_sequential_acquisition.cmca import allocate_cmca
from gymact.explore_sequential_acquisition.sensor import SensorCapability
from gymact.explore_sequential_acquisition.strategy import CandidateScore


def _sensor(
    letter: str,
    *,
    name: str,
    family: str,
    domain: str,
    cost: int,
    latency_ms: int,
) -> SensorCapability:
    return SensorCapability(
        name=name,
        family=family,
        domain=domain,
        generation=0,
        digest=letter * 64,
        cost=Fraction(cost),
        latency_ms=latency_ms,
    )


def _score(
    sensor: SensorCapability,
    *,
    information: Fraction,
    diversity: Fraction,
    uncertainty: Fraction = Fraction(0),
    regret: Fraction = Fraction(0),
) -> CandidateScore:
    return CandidateScore(
        sensor.digest,
        information,
        sensor.cost,
        uncertainty,
        regret,
        diversity,
    )


class CMCACourt(unittest.TestCase):
    def test_allocates_exact_budget_across_frontier_without_pruning_topology(self) -> None:
        a = _sensor("a", name="a", family="visual", domain="screen", cost=1, latency_ms=10)
        b = _sensor("b", name="b", family="event", domain="stream", cost=1, latency_ms=10)
        c = _sensor("c", name="c", family="visual", domain="screen", cost=2, latency_ms=20)
        candidates = (a, b, c)
        scores = {
            a.digest: _score(a, information=Fraction(4, 5), diversity=Fraction(1, 3)),
            b.digest: _score(b, information=Fraction(1, 2), diversity=Fraction(4, 5)),
            c.digest: _score(c, information=Fraction(1, 10), diversity=Fraction(1, 10)),
        }
        budget = Budget(cost=Fraction(10), latency_ms=100, samples=5)

        plan = allocate_cmca(candidates, scores, budget)

        self.assertEqual(
            tuple(item.sensor_digest for item in plan.allocations),
            tuple(sorted(scores)),
        )
        self.assertEqual(
            {item.sensor_digest for item in plan.allocations},
            {item.digest for item in candidates},
        )
        self.assertEqual(plan.frontier_digests, (a.digest, b.digest))
        self.assertEqual(
            sum((item.continuation_share for item in plan.allocations), Fraction(0)),
            1,
        )
        self.assertEqual(plan.allocated_cost, budget.cost)
        self.assertEqual(plan.allocated_latency_ms, budget.latency_ms)
        self.assertEqual(plan.allocated_samples, budget.samples)

        dominated = next(item for item in plan.allocations if item.sensor_digest == c.digest)
        self.assertEqual(dominated.reason, "DOMINATED")
        self.assertEqual(dominated.continuation_share, 0)
        self.assertEqual(dominated.allocated_cost, 0)
        self.assertEqual(dominated.allocated_latency_ms, 0)
        self.assertEqual(dominated.allocated_samples, 0)

    def test_preserves_missing_and_budget_inadmissible_candidates_as_zero_edges(self) -> None:
        admitted = _sensor("a", name="a", family="visual", domain="screen", cost=1, latency_ms=10)
        missing = _sensor("b", name="b", family="event", domain="stream", cost=1, latency_ms=10)
        expensive = _sensor("c", name="c", family="api", domain="remote", cost=20, latency_ms=10)
        budget = Budget(cost=Fraction(10), latency_ms=100, samples=3)
        scores = {
            admitted.digest: _score(
                admitted,
                information=Fraction(1, 2),
                diversity=Fraction(1, 2),
            ),
            expensive.digest: _score(
                expensive,
                information=Fraction(1),
                diversity=Fraction(1),
            ),
        }

        plan = allocate_cmca((missing, expensive, admitted), scores, budget)
        by_digest = {item.sensor_digest: item for item in plan.allocations}

        self.assertEqual(len(plan.allocations), 3)
        self.assertEqual(by_digest[missing.digest].reason, "REFUSED_MISSING_SCORE")
        self.assertEqual(
            by_digest[expensive.digest].reason,
            "REFUSED_BUDGET_INADMISSIBLE",
        )
        self.assertEqual(by_digest[missing.digest].continuation_share, 0)
        self.assertEqual(by_digest[expensive.digest].continuation_share, 0)
        self.assertEqual(by_digest[admitted.digest].continuation_share, 1)

    def test_is_deterministic_across_candidate_order(self) -> None:
        a = _sensor("a", name="a", family="visual", domain="screen", cost=1, latency_ms=10)
        b = _sensor("b", name="b", family="visual", domain="screen", cost=1, latency_ms=10)
        scores = {
            a.digest: _score(
                a,
                information=Fraction(2, 3),
                diversity=Fraction(1, 3),
                uncertainty=Fraction(1, 5),
            ),
            b.digest: _score(
                b,
                information=Fraction(1, 3),
                diversity=Fraction(2, 3),
                uncertainty=Fraction(1, 4),
            ),
        }
        budget = Budget(cost=Fraction(7), latency_ms=101, samples=7)

        self.assertEqual(
            allocate_cmca((a, b), scores, budget),
            allocate_cmca((b, a), scores, budget),
        )

    def test_refuses_when_no_candidate_is_lawful(self) -> None:
        candidate = _sensor(
            "a",
            name="a",
            family="visual",
            domain="screen",
            cost=2,
            latency_ms=10,
        )
        candidate_score = _score(
            candidate,
            information=Fraction(1),
            diversity=Fraction(1),
        )

        with self.assertRaisesRegex(ValueError, "REFUSED_NO_LAWFUL_CMCA_FRONTIER"):
            allocate_cmca(
                (candidate,),
                {candidate.digest: candidate_score},
                Budget(cost=Fraction(1), latency_ms=100, samples=1),
            )


if __name__ == "__main__":
    unittest.main()
