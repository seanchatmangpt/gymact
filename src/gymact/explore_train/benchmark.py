from dataclasses import dataclass

@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    successes: int
    trials: int

    @property
    def rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0


def benchmark(name: str, runner, cases: tuple[dict, ...], oracle) -> BenchmarkResult:
    successes = sum(1 for case in cases if oracle(case, runner(case)))
    return BenchmarkResult(name, successes, len(cases))
