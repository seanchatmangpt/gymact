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


def test_admits_structured_exact_subject_allowed_by_producer_schema():
    subject = {"kind": "drive", "serial": 42, "path": ["head", 7]}
    admitted = admit_envelope(envelope(exact_subject=subject))
    assert admitted.exact_subject == subject


def test_rejects_null_or_non_json_exact_subject():
    with pytest.raises(ValidationError):
        admit_envelope(envelope(exact_subject=None))

    with pytest.raises(ValidationError):
        admit_envelope(envelope(exact_subject=object()))


def test_rejects_contract_drift_authority_escalation_and_unknown_fields():
    with pytest.raises(ValidationError):
        admit_envelope(envelope(contract_digest="sha256:" + "0" * 64))

    with pytest.raises(ValidationError):
        admit_envelope(
            envelope(decision={"kind": "replan", "reason": "failed", "authority": "do"})
        )

    with pytest.raises(ValidationError):
        admit_envelope(envelope(unmodeled_authority="do"))
