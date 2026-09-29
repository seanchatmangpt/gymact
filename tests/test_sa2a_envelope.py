from pydantic import ValidationError
import pytest

from gymact.sa2a_envelope import (
    SA2A_REPLAN_CONTRACT_DIGEST,
    SA2AReplanEnvelope,
    admit_envelope,
)


def envelope(**updates):
    value = {
        "schema": "sa2a/replan-envelope/v1",
        "contract_digest": SA2A_REPLAN_CONTRACT_DIGEST,
        "exact_subject": "urn:subject:1",
        "receipt_id": "r1",
        "consequence": "failed",
        "decision": {"kind": "replan", "reason": "failed", "authority": "none"},
        "provider": "beam4pm",
        "projection_digest": None,
        "source_replay_key": "abc123",
    }
    value.update(updates)
    return value


def test_admits_exact_canonical_contract():
    admitted = admit_envelope(envelope())
    assert isinstance(admitted, SA2AReplanEnvelope)
    assert admitted.exact_subject == "urn:subject:1"


def test_rejects_contract_drift_and_authority_escalation():
    with pytest.raises(ValidationError):
        admit_envelope(envelope(contract_digest="sha256:" + "0" * 64))

    with pytest.raises(ValidationError):
        admit_envelope(
            envelope(decision={"kind": "replan", "reason": "failed", "authority": "do"})
        )
