from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class ObjectiveVector:
    sensor: str
    information: Fraction
    diversity: Fraction
    cost: Fraction
    latency: int


def dominates(a: ObjectiveVector, b: ObjectiveVector) -> bool:
    no_worse = (
        a.information >= b.information
        and a.diversity >= b.diversity
        and a.cost <= b.cost
        and a.latency <= b.latency
    )
    better = (
        a.information > b.information
        or a.diversity > b.diversity
        or a.cost < b.cost
        or a.latency < b.latency
    )
    return no_worse and better


def pareto_frontier(items: tuple[ObjectiveVector, ...]) -> tuple[ObjectiveVector, ...]:
    return tuple(
        item
        for item in items
        if not any(dominates(other, item) for other in items if other != item)
    )
