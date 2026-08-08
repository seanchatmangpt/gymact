import pytest

from gymact.transport import TransportKind, normalize_candidate, protocol_equivalent


def _payload() -> dict[str, object]:
    return {
        "episode_id": "ep-1",
        "action_ref": "urn:gymact:action:set",
        "subject": {
            "semantic_id": "urn:subject:1",
            "provider_ref": "urn:provider:1",
            "revision": "r1",
        },
        "payload": {"key": "x", "value": 1},
        "admission_digest": "abc",
        "idempotency_key": "idem-1",
    }


def test_equivalent_transports_normalize_to_same_candidate() -> None:
    envelopes = [
        normalize_candidate(kind, _payload())
        for kind in (
            TransportKind.CLI,
            TransportKind.REST,
            TransportKind.MCP,
            TransportKind.A2A,
        )
    ]
    assert protocol_equivalent(*envelopes)
    assert all(item.prepared() == envelopes[0].prepared() for item in envelopes)


def test_transport_cannot_smuggle_execution_authority() -> None:
    payload = _payload()
    payload["metadata"] = {"principal": "root"}
    with pytest.raises(ValueError, match="TRANSPORT_AUTHORITY_LEAK"):
        normalize_candidate(TransportKind.MCP, payload)


def test_transport_difference_is_not_equivalent() -> None:
    left = normalize_candidate(TransportKind.CLI, _payload())
    changed = _payload()
    changed["payload"] = {"key": "x", "value": 2}
    right = normalize_candidate(TransportKind.REST, changed)
    assert not protocol_equivalent(left, right)
