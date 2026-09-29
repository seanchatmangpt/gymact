"""Deterministic authority-free provider selection."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
from gymact.sa2a_provider import SA2ACandidateProvider, admit_provider
from gymact.sa2a_provider_health import SA2AProviderHealth, provider_is_selectable

def select_candidate_providers(providers: Iterable[SA2ACandidateProvider], *, health: Mapping[str, SA2AProviderHealth]|None=None, excluded: frozenset[str]=frozenset()) -> tuple[SA2ACandidateProvider,...]:
    states=health or {}
    admitted=[]
    for provider in providers:
        admit_provider(provider)
        if provider.id in excluded: continue
        if not provider_is_selectable(states.get(provider.id, SA2AProviderHealth.HEALTHY)): continue
        admitted.append(provider)
    return tuple(admitted)
