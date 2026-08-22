from dataclasses import dataclass


@dataclass(frozen=True)
class AhpResult:
    name: str
    priority: float


def normalize(matrix: dict[str, dict[str, float]]) -> tuple[AhpResult, ...]:
    names = sorted(matrix)
    if not names:
        return ()
    totals = {column: sum(matrix[row][column] for row in names) for column in names}
    results = []
    for row in names:
        value = sum(matrix[row][column] / totals[column] for column in names) / len(names)
        results.append(AhpResult(row, value))
    return tuple(sorted(results, key=lambda result: (-result.priority, result.name)))
