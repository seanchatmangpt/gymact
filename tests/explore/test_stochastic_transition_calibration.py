from collections import Counter


def deterministic_lcg(seed: int, n: int) -> list[float]:
    x = seed
    out = []
    for _ in range(n):
        x = (1103515245 * x + 12345) % (2**31)
        out.append(x / 2**31)
    return out


def test_empirical_transition_rate_is_bounded_and_replayable() -> None:
    samples = deterministic_lcg(7, 10_000)
    outcomes = ["success" if x < 0.7 else "failure" for x in samples]
    counts = Counter(outcomes)
    rate = counts["success"] / len(outcomes)
    assert 0.68 <= rate <= 0.72
    assert samples == deterministic_lcg(7, 10_000)
