"""Real admit_envelope transport tests for the A2A v1 <-> SA2A adapter (Chicago)."""

import pytest
from pydantic import ValidationError

from gymact.sa2a_envelope import SA2A_REPLAN_CONTRACT_DIGEST, SA2AReplanEnvelope
from gymact.sa2a_transport import a2a_task_to_envelope, envelope_to_artifact


def envelope_payload(**updates):
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


def a2a_task(payload, task_id="task-1", context_id="ctx-1"):
    return {
        "id": task_id,
        "taskId": task_id,
        "contextId": context_id,
        "status": {"state": "submitted"},
        "message": {
            "role": "user",
            "parts": [{"kind": "data", "data": payload}],
        },
    }


def test_valid_task_admits_envelope_with_verbatim_digest():
    payload = envelope_payload()
    admitted = a2a_task_to_envelope(a2a_task(payload))
    assert isinstance(admitted, SA2AReplanEnvelope)
    assert admitted.contract_digest == SA2A_REPLAN_CONTRACT_DIGEST
    assert admitted.exact_subject == "urn:subject:1"

    # The adapter is a pure transport: admitting the same payload directly
    # must yield the identical envelope.
    direct = admit_direct(payload)
    assert admitted.model_dump(mode="json") == direct.model_dump(mode="json")


def admit_direct(payload):
    from gymact.sa2a_envelope import admit_envelope

    return admit_envelope(payload)


def test_subject_mismatch_surfaces_typed_failed_state():
    # exact_subject=None -> SA2A_EXACT_SUBJECT_REQUIRED refusal, never silent.
    task = a2a_task(envelope_payload(exact_subject=None))
    result = a2a_task_to_envelope(task)
    assert isinstance(result, dict)
    assert result["status"]["state"] == "failed"
    code = result["status"]["message"]["parts"][0]["metadata"]["errorCode"]
    assert code == "SA2A_EXACT_SUBJECT_REQUIRED"
    assert result["id"] == "task-1"
    assert result["contextId"] == "ctx-1"


def test_digest_tamper_is_refused():
    task = a2a_task(envelope_payload(contract_digest="sha256:" + "0" * 64))
    result = a2a_task_to_envelope(task)
    assert isinstance(result, dict)
    assert result["status"]["state"] == "failed"
    code = result["status"]["message"]["parts"][0]["metadata"]["errorCode"]
    assert code == "SA2A_ENVELOPE_INVALID"


def test_missing_envelope_part_is_typed_failure():
    task = a2a_task(envelope_payload())
    task["message"]["parts"] = [{"kind": "text", "text": "hello"}]
    result = a2a_task_to_envelope(task)
    assert result["status"]["state"] == "failed"
    code = result["status"]["message"]["parts"][0]["metadata"]["errorCode"]
    assert code == "A2A_ENVELOPE_PART_NOT_FOUND"


def test_round_trip_artifact():
    envelope = a2a_task_to_envelope(a2a_task(envelope_payload()))
    artifact = envelope_to_artifact(envelope)
    assert artifact["artifactId"] == "sa2a-evolution-feedback-r1"
    (part,) = artifact["parts"]
    assert part["kind"] == "data"
    data = part["data"]
    assert data["receipt_id"] == "r1"
    assert data["exact_subject"] == "urn:subject:1"
    assert data["decision_kind"] == "replan"
    assert data["authority"] == "none"
    assert data["envelope_digest"].startswith("blake3:")
    # The artifact must be shaped as real A2A data parts.
    assert artifact["name"] == "SA2A Evolution Feedback"


def test_artifact_accepts_dict_envelope_and_refuses_invalid():
    artifact = envelope_to_artifact(envelope_payload())
    assert artifact["artifactId"] == "sa2a-evolution-feedback-r1"

    with pytest.raises(ValidationError):
        envelope_to_artifact(envelope_payload(contract_digest="sha256:" + "0" * 64))
