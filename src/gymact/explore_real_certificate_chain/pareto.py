from .selector import Candidate


def frontier(items: list[Candidate]) -> list[Candidate]:
    out = []
    for item in items:
        dominated = any(
            other is not item
            and other.independence >= item.independence
            and other.runtime_diversity >= item.runtime_diversity
            and other.cost <= item.cost
            and (
                other.independence > item.independence
                or other.runtime_diversity > item.runtime_diversity
                or other.cost < item.cost
            )
            for other in items
        )
        if not dominated:
            out.append(item)
    return sorted(out, key=lambda c: c.name)
