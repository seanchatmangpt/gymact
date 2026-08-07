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

import hashlib
import json
import os
import shutil
import subprocess
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
from gymact.ocel import write_ocel_log
from gymact.standing import require_standing

AUTHORITY = "urn:test:ggen-legacy-authority"
OBSERVE_CAPABILITY = "urn:gymact:ggen-legacy:capability:observe"
VERIFY_CAPABILITY = "urn:gymact:ggen-legacy:capability:verify"

GGEN_LEGACY_ROOT = Path(
    os.environ.get("GGEN_LEGACY_ROOT", str(Path.home() / "ggen-legacy"))
).resolve()

WASM4PM_ROOT = Path(os.environ.get("WASM4PM_ROOT", str(Path.home() / "wasm4pm"))).resolve()

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


@pytest.mark.asyncio
async def test_ocel_export_is_independently_validated_by_wasm4pm(tmp_path) -> None:
    """Drive the real ggen-legacy verifier lifecycle end to end, export the
    real Receipt trail as an OCEL 2.0 log, and get an independent, real,
    cross-language confirmation that the log is structurally valid by
    running it through wasm4pm's own Rust `wpm` CLI (a completely separate
    OCEL 2.0 parser from gymact's Python jsonschema validator) as a real
    subprocess. This proves the harness runs end to end for real -- it does
    not and should not launder ggen-legacy's own real standing (currently
    BUILD_BROKEN / release_admitted=false) into a false pass; that standing
    is recorded faithfully in the exported log, not overwritten.
    """
    require_standing(
        "LOCAL_CHECKOUT:wasm4pm",
        available=(WASM4PM_ROOT / "Cargo.toml").is_file() and shutil.which("cargo") is not None,
        reason=f"no wasm4pm checkout with cargo available at {WASM4PM_ROOT}",
    )

    runtime = authorized_runtime()
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="ggen-legacy",
            config={"root": str(GGEN_LEGACY_ROOT)},
            authority_ref=AUTHORITY,
            idempotency_key="ocel-materialize",
        )
    )
    episode = materialized.episode
    assert episode is not None
    receipts = [materialized.receipt]

    observe_action = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=OBSERVE_CAPABILITY,
            authority_ref=AUTHORITY,
            idempotency_key="ocel-observe",
        )
    )
    receipts.append(observe_action.receipt)

    verify_action = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=VERIFY_CAPABILITY,
            authority_ref=AUTHORITY,
            idempotency_key="ocel-verify",
        )
    )
    receipts.append(verify_action.receipt)

    checkpoint = await runtime.checkpoint(episode.episode_id)
    restored = await runtime.restore(episode.episode_id, checkpoint, authority_ref=AUTHORITY)
    receipts.append(restored)

    teardown_receipt = await runtime.teardown(episode.episode_id, authority_ref=AUTHORITY)
    receipts.append(teardown_receipt)

    # Real ggen-legacy standing is recorded faithfully, not asserted here as
    # a pass/fail -- this test validates the log's structure, not the
    # verifier's verdict on the repo.
    assert verify_action.observation is not None
    real_standing = verify_action.observation.state.get("standing")
    assert real_standing in {member.value for member in Standing}

    log_path = tmp_path / "ggen-legacy.ocel.json"
    log, digest = write_ocel_log(log_path, receipts)
    assert log_path.is_file()
    on_disk_digest = hashlib.sha256(log_path.read_bytes()).hexdigest()
    assert on_disk_digest == digest
    assert len(log["events"]) == len(receipts)

    # Minimal receipt envelope wasm4pm's `wpm receipt verify-ocel2` expects:
    # algorithms[].{expected_path.expected_ocel2, observed_path.observed_ocel2}.
    # Comparing the log against itself is a legitimate structural check here
    # -- the point is confirming wasm4pm's independently implemented Rust
    # OCEL 2.0 parser agrees the document is valid, not diffing two runs.
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(
        json.dumps(
            {
                "algorithms": [
                    {
                        "expected_path": {"expected_ocel2": log},
                        "observed_path": {"observed_ocel2": log},
                    }
                ]
            }
        )
    )

    # cwd (not --manifest-path) must be wasm4pm's own root so rustup picks up
    # its pinned nightly toolchain file -- wasm4pm-compat requires nightly-only
    # features (#![feature(generic_const_exprs)]) and fails to compile under
    # whatever toolchain the caller's own cwd would otherwise resolve to.
    result = subprocess.run(
        ["cargo", "run", "--bin", "wpm", "--", "receipt", "verify-ocel2", str(envelope_path)],
        cwd=str(WASM4PM_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert "PASS" in result.stdout, (
        f"wasm4pm did not independently confirm OCEL validity "
        f"(exit={result.returncode}):\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert result.returncode == 0
