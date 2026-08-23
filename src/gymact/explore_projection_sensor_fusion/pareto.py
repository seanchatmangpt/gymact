from .acquisition import AcquisitionCandidate


def dominates(left: AcquisitionCandidate, right: AcquisitionCandidate) -> bool:
    no_worse = (
        left.expected_discrimination >= right.expected_discrimination
        and left.independence_gain >= right.independence_gain
        and left.cost <= right.cost
        and left.latency_ms <= right.latency_ms
    )
    strict = (
        left.expected_discrimination > right.expected_discrimination
        or left.independence_gain > right.independence_gain
        or left.cost < right.cost
        or left.latency_ms < right.latency_ms
    )
    return no_worse and strict


def frontier(
    candidates: tuple[AcquisitionCandidate, ...],
) -> tuple[AcquisitionCandidate, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if not any(
            dominates(other, candidate)
            for other in candidates
            if other is not candidate
        )
    )
