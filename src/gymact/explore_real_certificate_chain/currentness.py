from dataclasses import dataclass


@dataclass(frozen=True)
class CertificateGeneration:
    generation: int
    digest: str


def latest_unique(items: list[CertificateGeneration]) -> CertificateGeneration:
    if not items:
        raise ValueError("STALE_CERTIFICATE")
    top = max(x.generation for x in items)
    current = {x.digest for x in items if x.generation == top}
    if len(current) != 1:
        raise ValueError("STALE_CERTIFICATE")
    return next(x for x in items if x.generation == top)
