"""Composed GymAct portable provider/recovery runtime; SELECT/CONSTRUCT only."""
from __future__ import annotations
from collections.abc import Mapping
from pydantic import JsonValue
from gymact.sa2a_envelope import SA2AReplanEnvelope, admit_envelope
from gymact.sa2a_failover import SA2AFailoverResult, propose_with_failover
from gymact.sa2a_provider import SA2ACandidateProvider
from gymact.sa2a_provider_health import SA2AProviderHealth
from gymact.sa2a_provider_selection import select_candidate_providers
from gymact.sa2a_reconciliation import reconcile_outcome

def run_provider_runtime(value: SA2AReplanEnvelope|dict[str,object], *, expected_subject:JsonValue, providers:tuple[SA2ACandidateProvider,...], health:Mapping[str,SA2AProviderHealth]|None=None, excluded:frozenset[str]=frozenset(), max_attempts:int|None=None) -> SA2AFailoverResult:
    envelope=admit_envelope(value)
    if envelope.exact_subject != expected_subject: raise ValueError("SA2A_STALE_SUBJECT_REFUSED")
    selected=select_candidate_providers(providers,health=health,excluded=excluded)
    result=propose_with_failover(envelope,selected,max_attempts=max_attempts)
    reconcile_outcome(result.envelope)
    return result
