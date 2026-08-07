"""Chicago-style: a real episode's real receipts become a real, schema-valid
OCEL 2.0 log -- and a standing claim about that episode is re-derived by
independently re-parsing the log, not trusted from prose.

This is the direct fix for "claims should be checked against OCEL v2, not
narrated": every assertion below either validates the log against the real
official OCEL 2.0 JSON Schema (jsonschema.validate, real format checking via
rfc3339-validator) or reconstructs the conformance verdict from the log's own
`events` array -- never from the in-memory `Receipt` objects a test could
otherwise (mis)report against.

Every episode in this file goes through `CubeCounterProvider`, which wraps
the real, externally-published `counter_cube.task.ReachTargetTask` (see
`gymact/gyms/cube_counter.py`) -- never `gymact.providers.MemoryProvider`
(GymAct's own synthetic reference world, exercised separately in
`tests/test_core.py`). `pytest.importorskip("counter_cube")` makes that
distinction load-bearing: if the real package is absent, this file skips by
name instead of silently substituting anything internal for it.
"""

from __future__ import annotations

import json

import pytest
from jsonschema.exceptions import ValidationError

pytest.importorskip("counter_cube")

from gymact import GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.cube_counter import CubeCounterProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log, write_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402


async def _run_real_counter_episode() -> list:
    gym = GymAct()
    gym.register_provider(CubeCounterProvider())
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="cube-counter", config={"target": 2})
    )
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    for _ in range(2):
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability="urn:gymact:cube-counter:capability:increment",
            )
        )
        receipts.append(result.receipt)

    receipts.append(await gym.teardown(episode_id))
    return receipts


async def test_real_episode_log_validates_against_the_real_ocel20_schema() -> None:
    receipts = await _run_real_counter_episode()

    log = receipts_to_ocel(receipts)

    # Must not raise -- real jsonschema.validate against the real vendored
    # official OCEL 2.0 schema.
    validate_ocel_log(log)


async def test_a_malformed_log_is_actually_rejected_not_rubber_stamped() -> None:
    receipts = await _run_real_counter_episode()
    log = receipts_to_ocel(receipts)

    # Corrupt a real, already-valid log the same way a bug could: drop the
    # required `time` field from one real event.
    del log["events"][0]["time"]

    with pytest.raises(ValidationError):
        validate_ocel_log(log)


async def test_conformance_verdict_is_re_derivable_from_the_log_alone() -> None:
    """The point of this test: don't trust the in-memory receipts' own
    operation order -- re-extract it from the persisted OCEL log's `events`
    (sorted by real `time`) and independently recompute conformance."""
    receipts = await _run_real_counter_episode()
    original_operations = [r.operation for r in receipts]
    original_result = ConformanceChecker().check(original_operations)

    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)

    events_by_time = sorted(log["events"], key=lambda e: e["time"])
    reconstructed_operations = [Operation(e["type"]) for e in events_by_time]

    reconstructed_result = ConformanceChecker().check(reconstructed_operations)

    assert reconstructed_operations == original_operations
    assert reconstructed_result == original_result
    assert reconstructed_result.conformant is True


async def test_write_ocel_log_persists_a_real_file_whose_digest_is_reproducible(
    tmp_path,
) -> None:
    receipts = await _run_real_counter_episode()

    log_path = tmp_path / "episode.ocel.json"
    log, digest = write_ocel_log(log_path, receipts)

    assert log_path.exists()
    on_disk = json.loads(log_path.read_text())
    assert on_disk == log

    # The whole point of citing a digest in a ledger is that a third party
    # can run `sha256sum <file>` themselves and get the same answer -- not
    # re-run our Python and trust a different serialization matches. Compute
    # the digest completely independently of `write_ocel_log`'s internals.
    import hashlib

    independently_computed = hashlib.sha256(log_path.read_bytes()).hexdigest()
    assert independently_computed == digest

    # Re-digesting the same real receipts must reproduce the same real digest
    # -- a claim citing this digest is independently checkable, not asserted.
    _log_again, digest_again = write_ocel_log(tmp_path / "episode2.ocel.json", receipts)
    assert digest_again == digest


async def test_empty_receipt_list_refuses_rather_than_producing_a_fake_empty_log() -> None:
    with pytest.raises(ValueError, match="empty receipt list"):
        receipts_to_ocel([])
