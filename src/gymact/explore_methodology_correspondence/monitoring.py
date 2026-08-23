from dataclasses import dataclass

@dataclass(frozen=True)
class Drift:
    expected: str
    observed: str
    changed: bool

def monitor(expected_digest: str, observed_digest: str) -> Drift:
    return Drift(expected_digest, observed_digest, expected_digest != observed_digest)
