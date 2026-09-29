"""Provider health is selection evidence, never authority."""
from __future__ import annotations
from enum import StrEnum
class SA2AProviderHealth(StrEnum):
    HEALTHY="healthy"; DEGRADED="degraded"; EXHAUSTED="exhausted"; FENCED="fenced"
def provider_is_selectable(state: SA2AProviderHealth) -> bool:
    return state in {SA2AProviderHealth.HEALTHY, SA2AProviderHealth.DEGRADED}
