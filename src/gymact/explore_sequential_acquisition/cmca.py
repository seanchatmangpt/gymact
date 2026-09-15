"""CMCA allocation over the existing lawful acquisition frontier.

CMCA is a SELECT-only meta-policy. It does not create sensors, mutate the possibility
topology, acquire observations, or cross a BRCE DO boundary. It allocates the existing
``Budget`` across the existing Pareto frontier while retaining every supplied candidate
in the returned topology, including candidates receiving zero allocation.

Allocation mixes two exact-rational scales:

1. global evidence/continuation weight across the whole frontier; and
2. equal mass across independent ``(family, domain)`` branches, distributed locally
   by the same continuation weight.

The 50/50 mixture prevents one dense branch from consuming the entire budget solely
because it contains more candidates, while still allowing evidence to concentrate
resources inside and across branches. No floating-point ranking is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .budget import Budget
from .frontier import ObjectiveVector, pareto_frontier
from .sensor import SensorCapability
from .strategy import CandidateScore


@dataclass(frozen=True)
class CMCAAllocation:
    sensor_digest: str
    sensor_name: str
    independence_key: tuple[str, str]
    on_frontier: bool
    continuation_share: Fraction
    allocated_cost: Fraction
    allocated_latency_ms: int
    allocated_samples: int
    reason: str

    def __post_init__(self) -> None:
        if self.continuation_share < 0 or self.continuation_share > 1:
            raise ValueError("REFUSED_INVALID_CMCA_SHARE")
        if self.allocated_cost < 0 or self.allocated_latency_ms < 0 or self.allocated_samples < 0:
            raise ValueError("REFUSED_INVALID_CMCA_ALLOCATION")


@dataclass(frozen=True)
class CMCAPlan:
    source_budget: Budget
    allocations: tuple[CMCAAllocation, ...]

    def __post_init__(self) -> None:
        digests = tuple(item.sensor_digest for item in self.allocations)
        if len(digests) != len(set(digests)):
            raise ValueError("REFUSED_DUPLICATE_CMCA_SENSOR")
        if sum((item.continuation_share for item in self.allocations), Fraction(0)) != 1:
            raise ValueError("REFUSED_CMCA_SHARE_NOT_CLOSED")
        if self.allocated_cost > self.source_budget.cost:
            raise ValueError("REFUSED_CMCA_COST_EXCEEDED")
        if self.allocated_latency_ms > self.source_budget.latency_ms:
            raise ValueError("REFUSED_CMCA_LATENCY_EXCEEDED")
        if self.allocated_samples > self.source_budget.samples:
            raise ValueError("REFUSED_CMCA_SAMPLES_EXCEEDED")

    @property
    def allocated_cost(self) -> Fraction:
        return sum((item.allocated_cost for item in self.allocations), Fraction(0))

    @property
    def allocated_latency_ms(self) -> int:
        return sum(item.allocated_latency_ms for item in self.allocations)

    @property
    def allocated_samples(self) -> int:
        return sum(item.allocated_samples for item in self.allocations)

    @property
    def frontier_digests(self) -> tuple[str, ...]:
        return tuple(item.sensor_digest for item in self.allocations if item.on_frontier)


def _positive(value: Fraction) -> Fraction:
    return max(value, Fraction(0))


def _continuation_weight(score: CandidateScore) -> Fraction:
    """Exact-rational option value used only for allocation, never semantic standing."""

    regret = _positive(score.regret)
    return (
        Fraction(1)
        + _positive(score.information)
        + _positive(score.diversity)
        + _positive(score.uncertainty)
        + Fraction(1, 1 + regret)
    )


def _apportion_integer(total: int, shares: dict[str, Fraction]) -> dict[str, int]:
    """Largest-remainder apportionment with digest-stable tie breaking."""

    if total < 0:
        raise ValueError("REFUSED_INVALID_CMCA_INTEGER_BUDGET")
    if not shares:
        return {}

    raw = {key: share * total for key, share in shares.items()}
    result = {
        key: value.numerator // value.denominator
        for key, value in raw.items()
    }
    remaining = total - sum(result.values())
    remainder_order = sorted(
        shares,
        key=lambda key: (raw[key] - result[key], key),
        reverse=True,
    )
    for key in remainder_order[:remaining]:
        result[key] += 1
    return result


def allocate_cmca(
    candidates: tuple[SensorCapability, ...],
    scores: dict[str, CandidateScore],
    budget: Budget,
) -> CMCAPlan:
    """Allocate a budget across the lawful Pareto frontier without pruning topology.

    Candidates missing evidence or individually inadmissible under the source budget are
    retained with zero allocation. Candidates dominated on the lawful frontier are also
    retained with zero allocation. At least one lawful scored candidate is required.
    """

    if not candidates:
        raise ValueError("REFUSED_NO_CMCA_CANDIDATES")

    digests = tuple(candidate.digest for candidate in candidates)
    if len(digests) != len(set(digests)):
        raise ValueError("REFUSED_DUPLICATE_CMCA_SENSOR")

    lawful: list[SensorCapability] = []
    reason_by_digest: dict[str, str] = {}
    for candidate in candidates:
        if candidate.digest not in scores:
            reason_by_digest[candidate.digest] = "REFUSED_MISSING_SCORE"
            continue
        if not budget.admits(
            cost=candidate.cost,
            latency_ms=candidate.latency_ms,
            samples=1,
        ):
            reason_by_digest[candidate.digest] = "REFUSED_BUDGET_INADMISSIBLE"
            continue
        lawful.append(candidate)

    if not lawful:
        raise ValueError("REFUSED_NO_LAWFUL_CMCA_FRONTIER")

    objectives = tuple(
        ObjectiveVector(
            sensor=candidate.digest,
            information=scores[candidate.digest].information,
            diversity=scores[candidate.digest].diversity,
            cost=candidate.cost,
            latency=candidate.latency_ms,
        )
        for candidate in lawful
    )
    frontier_digests = {item.sensor for item in pareto_frontier(objectives)}

    frontier_candidates = tuple(
        candidate for candidate in lawful if candidate.digest in frontier_digests
    )
    if not frontier_candidates:
        raise ValueError("REFUSED_EMPTY_CMCA_FRONTIER")

    weights = {
        candidate.digest: _continuation_weight(scores[candidate.digest])
        for candidate in frontier_candidates
    }
    total_weight = sum(weights.values(), Fraction(0))

    groups: dict[tuple[str, str], list[SensorCapability]] = {}
    for candidate in frontier_candidates:
        groups.setdefault(candidate.independence_key, []).append(candidate)
    group_count = len(groups)

    group_weights = {
        key: sum((weights[item.digest] for item in members), Fraction(0))
        for key, members in groups.items()
    }

    shares: dict[str, Fraction] = {}
    for candidate in frontier_candidates:
        global_share = weights[candidate.digest] / total_weight
        local_share = (
            Fraction(1, group_count)
            * weights[candidate.digest]
            / group_weights[candidate.independence_key]
        )
        shares[candidate.digest] = (global_share + local_share) / 2

    if sum(shares.values(), Fraction(0)) != 1:
        raise ValueError("REFUSED_CMCA_SHARE_NOT_CLOSED")

    latency = _apportion_integer(budget.latency_ms, shares)
    samples = _apportion_integer(budget.samples, shares)

    allocations: list[CMCAAllocation] = []
    for candidate in sorted(candidates, key=lambda item: item.digest):
        if candidate.digest in frontier_digests:
            share = shares[candidate.digest]
            allocations.append(
                CMCAAllocation(
                    sensor_digest=candidate.digest,
                    sensor_name=candidate.name,
                    independence_key=candidate.independence_key,
                    on_frontier=True,
                    continuation_share=share,
                    allocated_cost=budget.cost * share,
                    allocated_latency_ms=latency[candidate.digest],
                    allocated_samples=samples[candidate.digest],
                    reason="ALLOCATED",
                )
            )
            continue

        if candidate.digest in reason_by_digest:
            reason = reason_by_digest[candidate.digest]
        else:
            reason = "DOMINATED"
        allocations.append(
            CMCAAllocation(
                sensor_digest=candidate.digest,
                sensor_name=candidate.name,
                independence_key=candidate.independence_key,
                on_frontier=False,
                continuation_share=Fraction(0),
                allocated_cost=Fraction(0),
                allocated_latency_ms=0,
                allocated_samples=0,
                reason=reason,
            )
        )

    return CMCAPlan(source_budget=budget, allocations=tuple(allocations))
