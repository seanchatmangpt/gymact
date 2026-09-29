"""Bounded provider-local failover preserving portable identity."""
from __future__ import annotations
from dataclasses import dataclass
from gymact.sa2a_envelope import SA2AReplanEnvelope
from gymact.sa2a_provider import SA2ACandidateProvider, admit_provider

@dataclass(frozen=True)
class SA2AFailoverResult:
    envelope: SA2AReplanEnvelope
    provider_id: str
    excluded: tuple[str,...]

def propose_with_failover(envelope: SA2AReplanEnvelope, providers: tuple[SA2ACandidateProvider,...], *, max_attempts:int|None=None) -> SA2AFailoverResult:
    limit=max(0, len(providers) if max_attempts is None else max_attempts)
    excluded=[]
    for provider in providers[:limit]:
        try:
            admit_provider(provider)
            candidate=provider.propose(envelope)
            if candidate.decision.authority != "none": raise ValueError("SA2A_CANDIDATE_AUTHORITY_REFUSED")
            if candidate.exact_subject != envelope.exact_subject: raise ValueError("SA2A_SUBJECT_DRIFT")
            if candidate.receipt_id != envelope.receipt_id: raise ValueError("SA2A_RECEIPT_DRIFT")
            if candidate.source_replay_key != envelope.source_replay_key: raise ValueError("SA2A_REPLAY_DRIFT")
            return SA2AFailoverResult(candidate, provider.id, tuple(excluded))
        except Exception:
            excluded.append(provider.id)
    raise RuntimeError("SA2A_PROVIDERS_EXHAUSTED:"+",".join(excluded))
