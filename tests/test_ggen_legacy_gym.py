"""Chicago-style (real subprocess, real filesystem, no mocks) tests for the
ggen-legacy verifier bridge, run against this session's actual ggen-legacy
checkout.

This module claims standing "LOCAL_CHECKOUT:ggen-legacy". Per
`gymact.standing.require_standing`, the real checkout is the default: if
`~/ggen-legacy` (or `$GGEN_LEGACY_ROOT`) isn't present, this module now
FAILS unless the run explicitly sets `GYMACT_ALLOW_DEGRADED_STANDINGS` to
include "LOCAL_CHECKOUT:ggen-legacy" (or "*") -- a skip here is something a
run must opt into, never something it silently gets.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gymact import (
    ActuationIntent,
    AllowListAuthorityResolver,
    GymAct,
    MaterializationIntent,
    Standing,
)
from gymact.gyms.ggen_legacy import GGEN_LEGACY_CAPABILITIES, GgenLegacyVerifierProvider
from gymact.standing import require_standing

AUTHORITY = "urn:test:ggen-legacy-authority"
OBSERVE_CAPABILITY = "urn:gymact:ggen-legacy:capability:observe"
VERIFY_CAPABILITY = "urn:gymact:ggen-legacy:capability:verify"

GGEN_LEGACY_ROOT = Path(
    os.environ.get("GGEN_LEGACY_ROOT", str(Path.home() / "ggen-legacy"))
).resolve()

require_standing(
    "LOCAL_CHECKOUT:ggen-legacy",
    available=(GGEN_LEGACY_ROOT / "tools" / "v26.8.1" / "Cargo.toml").is_file(),
    reason=f"no ggen-legacy checkout found at {GGEN_LEGACY_ROOT}",
)


def authorized_runtime() -> GymAct:
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    runtime.register_provider(GgenLegacyVerifierProvider())
    return runtime


def test_capabilities_conform_to_profile() -> None:
    runtime = GymAct()
    validation = runtime.profile.validate_capabilities(GGEN_LEGACY_CAPABILITIES)
    assert validation.conforms, validation.report_text
    assert {c.iri for c in GGEN_LEGACY_CAPABILITIES} == {OBSERVE_CAPABILITY, VERIFY_CAPABILITY}


@pytest.mark.asyncio
async def test_materialize_refuses_a_root_without_a_v26_8_1_workspace(tmp_path) -> None:
    runtime = authorized_runtime()
    result = await runtime.materialize(
        MaterializationIntent(
            provider="ggen-legacy",
            config={"root": str(tmp_path)},
            authority_ref=AUTHORITY,
            idempotency_key="bad-root",
        )
    )
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason == "PROVIDER_ERROR:TypeError"


@pytest.mark.asyncio
async def test_materialize_requires_authority_by_default() -> None:
    runtime = GymAct()
    runtime.register_provider(GgenLegacyVerifierProvider())
    result = await runtime.materialize(
        MaterializationIntent(
            provider="ggen-legacy",
            config={"root": str(GGEN_LEGACY_ROOT)},
            idempotency_key="no-authority",
        )
    )
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "LIVE_AUTHORITY_REQUIRED"


@pytest.mark.asyncio
async def test_observe_and_verify_capabilities_run_the_real_verifier() -> None:
    runtime = authorized_runtime()
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="ggen-legacy",
            config={"root": str(GGEN_LEGACY_ROOT)},
            authority_ref=AUTHORITY,
            idempotency_key="observe-verify-materialize",
        )
    )
    assert materialized.accepted is True
    episode = materialized.episode
    assert episode is not None

    capabilities = runtime.capabilities(episode.episode_id)
    assert {item.iri for item in capabilities} == {OBSERVE_CAPABILITY, VERIFY_CAPABILITY}

    observe_action = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=OBSERVE_CAPABILITY,
            authority_ref=AUTHORITY,
            idempotency_key="run-observe",
        )
    )
    assert observe_action.accepted is True
    assert observe_action.observation is not None
    report = observe_action.observation.state
    assert report.get("schema_version") == "ggen.v26.8.1.verifier-report/1"
    # The verifier's own standing vocabulary is a subset of gymact's Standing enum.
    assert report.get("standing") in {member.value for member in Standing}

    verification = await runtime.verify(episode.episode_id, {"standing": report["standing"]})
    assert verification.passed is True

    # Strict mode runs the same binary without --observe-only. It may refuse
    # (exit 2) on a repo that isn't release-admitted -- that's a real,
    # observed result, not a gymact-level failure: the actuation itself must
    # still be accepted.
    verify_action = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=VERIFY_CAPABILITY,
            authority_ref=AUTHORITY,
            idempotency_key="run-verify",
        )
    )
    assert verify_action.accepted is True
    assert verify_action.observation is not None
    strict_report = verify_action.observation.state
    assert strict_report.get("schema_version") == "ggen.v26.8.1.verifier-report/1"
    assert "release_admitted" in strict_report

    await runtime.teardown(episode.episode_id, authority_ref=AUTHORITY)


@pytest.mark.asyncio
async def test_checkpoint_restore_round_trips_the_evidence() -> None:
    runtime = authorized_runtime()
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="ggen-legacy",
            config={"root": str(GGEN_LEGACY_ROOT)},
            authority_ref=AUTHORITY,
            idempotency_key="checkpoint-materialize",
        )
    )
    episode = materialized.episode
    assert episode is not None

    first = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=OBSERVE_CAPABILITY,
            authority_ref=AUTHORITY,
            idempotency_key="checkpoint-observe-1",
        )
    )
    assert first.observation is not None
    checkpoint = await runtime.checkpoint(episode.episode_id)
    assert checkpoint["report"] == first.observation.state

    second = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=OBSERVE_CAPABILITY,
            authority_ref=AUTHORITY,
            idempotency_key="checkpoint-observe-2",
        )
    )
    assert second.observation is not None
    # Idempotent verifier: same repo state, same content, so this is a
    # meaningful round-trip check even though the two reports are equal.
    assert second.observation.state == first.observation.state

    restored = await runtime.restore(episode.episode_id, checkpoint, authority_ref=AUTHORITY)
    assert restored.standing == Standing.ALIVE
    observed_after_restore = await runtime.observe(episode.episode_id)
    assert observed_after_restore.state == first.observation.state

    await runtime.teardown(episode.episode_id, authority_ref=AUTHORITY)
