from enum import StrEnum

from .acquisition import AcquisitionCandidate


class Selector(StrEnum):
    MAX_DISCRIMINATION = "MAX_DISCRIMINATION"
    MAX_INDEPENDENCE_GAIN = "MAX_INDEPENDENCE_GAIN"
    MIN_COST = "MIN_COST"
    MINIMAX_LATENCY = "MINIMAX_LATENCY"


def select(
    candidates: tuple[AcquisitionCandidate, ...],
    strategy: Selector,
) -> AcquisitionCandidate | None:
    if not candidates:
        return None
    key = {
        Selector.MAX_DISCRIMINATION: lambda c: (-c.expected_discrimination, c.sensor_id),
        Selector.MAX_INDEPENDENCE_GAIN: lambda c: (-c.independence_gain, c.sensor_id),
        Selector.MIN_COST: lambda c: (c.cost, c.sensor_id),
        Selector.MINIMAX_LATENCY: lambda c: (c.latency_ms, c.sensor_id),
    }[strategy]
    return min(candidates, key=key)
