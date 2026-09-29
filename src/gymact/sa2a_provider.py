"""Authority-free candidate provider protocol for portable SA2A recovery."""
from __future__ import annotations
from typing import Protocol
from gymact.sa2a_envelope import SA2AReplanEnvelope

class SA2ACandidateProvider(Protocol):
    id: str
    authority: str
    def propose(self, envelope: SA2AReplanEnvelope) -> SA2AReplanEnvelope: ...

def admit_provider(provider: SA2ACandidateProvider) -> SA2ACandidateProvider:
    if not provider.id:
        raise ValueError("SA2A_PROVIDER_ID_REQUIRED")
    if provider.authority != "none":
        raise ValueError("SA2A_PROVIDER_AUTHORITY_REFUSED")
    return provider
