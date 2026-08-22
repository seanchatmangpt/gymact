from dataclasses import dataclass

@dataclass(frozen=True)
class AhpResult:
    name: str
    priority: float


def normalize(matrix: dict[str, dict[str, float]]) -> tuple[AhpResult, ...]:
    names = sorted(matrix)
    if not names:
        return ()
    totals = {col: sum(matrix[row][col] for row in names) for col in names}
    results = []
    for row in names:
        value = sum(matrix[row][col] / totals[col] for col in names) / len(names)
        results.append(AhpResult(row, value))
    return tuple(sorted(results, key=lambda r: (-r.priority, r.name)))
