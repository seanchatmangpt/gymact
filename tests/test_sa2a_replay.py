import pytest

from gymact.sa2a_envelope import SA2A_REPLAN_CONTRACT_DIGEST
from gymact.sa2a_replay import bind_sa2a_replay


def envelope(replay_key):
    return {
        "schema": "sa2a/replan-envelope/v1",
        "contract_digest": SA2A_REPLAN_CONTRACT_DIGEST,
        "exact_subject": "urn:subject:1",
        "receipt_id": "r1",
        "consequence": "failed",
        "decision": {"kind": "replan", "reason": "failed", "authority": "none"},
        "provider": "gymact",
        "projection_digest": None,
        "source_replay_key": replay_key,
    }


def test_replay_binding_preserves_upstream_key():
    replay = bind_sa2a_replay(envelope("replay-123"))
    assert replay.source_replay_key == "replay-123"
    assert replay.authority == "none"


def test_replay_binding_never_invents_missing_identity():
    with pytest.raises(ValueError, match="SA2A_SOURCE_REPLAY_KEY_REQUIRED"):
        bind_sa2a_replay(envelope(None))
