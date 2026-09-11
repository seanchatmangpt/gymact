from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderResult:
    provider: str
    implementation: str
    semantic_digest: str
    result_digest: str


def require_differential_equivalence(results: list[ProviderResult]) -> bool:
    if len({r.provider for r in results}) < 2 or len({r.implementation for r in results}) < 2:
        raise ValueError("REFUSED[INSUFFICIENT_PROVIDER_INDEPENDENCE]")
    if len({(r.semantic_digest, r.result_digest) for r in results}) != 1:
        raise ValueError("REFUSED[PROVIDER_DIVERGENCE]")
    return True
