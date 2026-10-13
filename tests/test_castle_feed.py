"""Chicago-style court for the gymact -> castle feed adapter.

The subject under test is the real middle adapter between gymact's real
`Receipt` trail and castle's only OCEL JSON parser
(`castle::xaas_feed::parse_xaas_ndjson`, castle `src/xaas_feed.rs`): real
receipts in, exact castle-dialect ndjson out, fail-closed typed refusals
on malformed input. No mocks: receipts come from a real GymAct episode on
the real in-process `MemoryProvider` reference world plus real `Receipt`
model construction (the same frozen pydantic model the runtime returns).
"""

from __future__ import annotations

import json

import pytest

from gymact.castle_feed import (
    CastleFeedRefused,
    receipts_to_castle_ndjson,
    validate_castle_feed_line,
)
from gymact.models import ActuationIntent, MaterializationIntent, Operation, Receipt, Standing

TIME = "2026-10-13T00:00:00.000000+00:00"


def _receipt(**overrides) -> Receipt:
    """A real `Receipt` (frozen pydantic model with real validators)."""
    defaults = {
        "receipt_id": f"r-{_receipt.counter:03d}",
        "occurred_at": TIME,
        "episode_id": "ep-1",
        "operation": Operation.OBSERVE,
        "standing": Standing.ALIVE,
        "subject_ref": "env:memory:1",
        "capability_ref": "urn:gymact:memory:capability:increment",
    }
    _receipt.counter += 1
    return Receipt(**{**defaults, **overrides})


_receipt.counter = 0


def _lines(receipts, **kw):
    ndjson = receipts_to_castle_ndjson(receipts, **kw)
    return [json.loads(line) for line in ndjson.splitlines()]


async def _real_episode_receipts():
    """A real GymAct episode's real receipt trail on the reference world."""
    from gymact import GymAct
    from gymact.providers import MemoryProvider

    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    receipts = []
    result = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"k": 1}},
            idempotency_key="castle-feed-fixture",
        )
    )
    receipts.append(result.receipt)
    episode_id = result.episode.episode_id
    for _ in range(2):
        result = await runtime.act(
            ActuationIntent(
                episode_id=episode_id,
                capability="urn:gymact:memory:capability:increment",
            )
        )
        receipts.append(result.receipt)
    receipts.append(await runtime.teardown(episode_id))
    return receipts


async def test_real_episode_receipts_convert_and_validate() -> None:
    receipts = await _real_episode_receipts()
    assert len(receipts) == 4  # materialize, act, act, teardown
    lines = _lines(receipts)
    assert len(lines) == 4
    for i, doc in enumerate(lines):
        validate_castle_feed_line(json.dumps(doc))  # must not raise
        event = doc["ocel:events"][0]
        assert event["id"] == receipts[i].receipt_id
        assert event["type"] == receipts[i].operation.value
        assert event["time"] == receipts[i].occurred_at
        assert event["attributes"]["authority"] == "none"
        assert event["attributes"]["provenance"] == "observation_only"


async def test_every_operation_value_is_covered_totality() -> None:
    for op in Operation:
        _receipt.counter = 0
        receipt = _receipt(operation=op)
        docs = _lines([receipt])
        doc = docs[0]
        validate_castle_feed_line(json.dumps(doc))
        assert doc["ocel:events"][0]["type"] == op.value
        assert {"name": op.value} in doc["ocel:eventTypes"]


def test_caller_supplied_timestamps_are_used_and_validated() -> None:
    _receipt.counter = 0
    receipts = [_receipt(), _receipt()]
    stamps = ["2026-01-02T03:04:05Z", "2026-01-02T03:04:06+00:00"]

    docs = _lines(receipts, timestamps=stamps)
    assert [d["ocel:events"][0]["time"] for d in docs] == stamps
    assert docs[0]["ocel:events"][0]["time"] != receipts[0].occurred_at

    with pytest.raises(CastleFeedRefused) as bad_time:
        receipts_to_castle_ndjson(receipts, timestamps=["not-a-time", stamps[1]])
    assert "REFUSED:INVALID_EVENT_TIME" in str(bad_time.value)

    with pytest.raises(CastleFeedRefused) as bad_len:
        receipts_to_castle_ndjson(receipts, timestamps=[stamps[0]])
    assert "REFUSED:TIMESTAMP_BATCH_LENGTH_MISMATCH" in str(bad_len.value)


def test_malformed_receipts_refuse_fail_closed_typed() -> None:
    with pytest.raises(CastleFeedRefused) as empty:
        receipts_to_castle_ndjson([])
    assert "REFUSED:EMPTY_RECEIPT_BATCH" in str(empty.value)

    with pytest.raises(CastleFeedRefused) as wrong_type:
        receipts_to_castle_ndjson(["not-a-receipt"])
    assert "REFUSED:NOT_A_GYMACT_RECEIPT: got str" in str(wrong_type.value)

    _receipt.counter = 0
    bad_id = _receipt().model_copy(update={"receipt_id": ""})
    with pytest.raises(CastleFeedRefused) as empty_id:
        receipts_to_castle_ndjson([bad_id])
    assert "REFUSED:INVALID_RECEIPT_ID" in str(empty_id.value)

    naive = _receipt().model_copy(update={"occurred_at": "2026-10-13T00:00:00"})
    with pytest.raises(CastleFeedRefused) as no_offset:
        receipts_to_castle_ndjson([naive])
    assert "REFUSED:INVALID_EVENT_TIME" in str(no_offset.value)


def test_determinism_identical_bytes_two_runs() -> None:
    _receipt.counter = 0
    receipts = [
        _receipt(operation=Operation.ACT, standing=Standing.PARTIAL_ALIVE, reason="act"),
        _receipt(operation=Operation.VERIFY, standing=Standing.REFUSED, reason=None),
        _receipt(operation=Operation.DISCOVER),
    ]
    first = receipts_to_castle_ndjson(receipts)
    second = receipts_to_castle_ndjson(receipts)
    assert first == second
    assert first.encode() == second.encode()


def test_sabotage_twin_validator_refuses_corrupted_line() -> None:
    """Sabotage a real emitted line the way a bug could; the emitter-side
    validator (castle parser law mirror) must refuse, never rubber-stamp."""
    _receipt.counter = 0
    doc = _lines([_receipt()])[0]
    del doc["ocel:events"][0]["time"]
    with pytest.raises(CastleFeedRefused) as no_time:
        validate_castle_feed_line(json.dumps(doc))
    assert "missing required key" in str(no_time.value)

    doc = _lines([_receipt()])[0]
    rel = doc["ocel:events"][0]["relationships"][0]
    del rel["qualifier"]
    with pytest.raises(CastleFeedRefused) as bad_rel:
        validate_castle_feed_line(json.dumps(doc))
    assert "objectId" in str(bad_rel.value)

    doc = _lines([_receipt()])[0]
    doc["ocel:events"][0]["extra"] = "x"
    with pytest.raises(CastleFeedRefused) as extra_key:
        validate_castle_feed_line(json.dumps(doc))
    assert "closed vocabulary" in str(extra_key.value)
