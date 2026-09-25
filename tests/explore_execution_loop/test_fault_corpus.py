"""Manifest-driven fault corpus runner.

Every scenario in scenario_manifest.json is executed against the real kernel
(``gymact.execution_loop.AutonomousLoop``) with in-process fakes, then:

1. terminal outcome must be in the scenario's expected legal outcome set;
2. episode standings must be legal (never ASSISTED -> AUTONOMOUS, never an
   illegal outcome);
3. every required OCEL fault-marker event must have been emitted;
4. the assembled OCEL 2.0 log must pass ``gymact.ocel.validate_ocel_log``
   (the vendored official schema);
5. runs are deterministic: same seed twice -> identical outcome and identical
   event digest;
6. scenario-specific post-conditions (exactly-once, substitution target,
   backoff clock) must hold.
"""

from __future__ import annotations

import pytest

from gymact.execution_loop import IllegalOutcome, LegalOutcome, loop_log
from gymact.ocel import validate_ocel_log


def _run_built(built):
    results = built.run()
    for result in results:
        # no code path may produce the illegal outcome
        assert result.outcome != IllegalOutcome.WAIT_FOR_HUMAN_TO_NOTICE.value
        assert result.asserted_illegal_outcome is None
        assert result.outcome in {member.value for member in LegalOutcome}
    return results


def test_scenario_runner(manifest, scenario, seed, court):
    builder = court.BUILDERS[scenario["id"]]
    built = builder(seed, inject=True)
    results = _run_built(built)

    terminal = results[-1].outcome
    assert terminal in scenario["expected_legal_outcomes"], (
        f"{scenario['id']}: terminal {terminal!r} not in expected "
        f"{scenario['expected_legal_outcomes']}; reason={results[-1].typed_reason}"
    )

    expected_standing = scenario.get("expected_standing")
    if expected_standing is not None:
        assert results[-1].standing.value == expected_standing, (
            f"{scenario['id']}: standing {results[-1].standing.value!r} != "
            f"{expected_standing!r}"
        )

    expected_broken = scenario.get("expected_broken_term")
    if expected_broken is not None:
        assert results[-1].broken_term is not None
        assert results[-1].broken_term.value == expected_broken

    court.assert_required_events(results, scenario["required_ocel_events"])
    court.assert_no_illegal_outcome(results)

    if built.post is not None:
        built.post(results)

    # episode standing law: the loop starts AUTONOMOUS and may only leave it
    # for typed blocked/failed standings; ASSISTED -> AUTONOMOUS is guarded
    # by EpisodeStanding.transition and covered in test_illegal_outcomes.py.
    episode = results[-1].episode_standing.value
    assert episode in {"AUTONOMOUS", "BLOCKED_AUTHORITY", "BLOCKED_INFORMATION", "FAILED"}


def test_ocel_log_validates_against_official_schema(manifest, scenario, seed, court):
    builder = court.BUILDERS[scenario["id"]]
    built = builder(seed, inject=True)
    results = built.run()
    log = loop_log(results, seed=seed)
    validate_ocel_log(log)  # must not raise


def test_scenario_determinism(manifest, scenario, seed, court):
    builder = court.BUILDERS[scenario["id"]]
    first = builder(seed, inject=True)
    second = builder(seed, inject=True)
    results_a = _run_built(first)
    results_b = _run_built(second)
    assert [r.outcome for r in results_a] == [r.outcome for r in results_b]
    assert [r.standing for r in results_a] == [r.standing for r in results_b]
    assert [r.typed_reason for r in results_a] == [r.typed_reason for r in results_b]
    assert court.results_digest(results_a) == court.results_digest(results_b), (
        f"{scenario['id']}(seed={seed}): event streams are not byte-deterministic"
    )


def test_every_corpus_scenario_has_a_builder(manifest, court):
    missing = [
        s["id"]
        for s in manifest["scenarios"]
        if s["id"] not in court.BUILDERS
        and s["id"] not in court.GUARD_SCENARIO_IDS
    ]
    assert not missing, f"manifest scenarios without builders: {missing}"


def test_required_families_covered(manifest):
    required = {
        "worker_sigkill",
        "provider_disappearance",
        "network_partition",
        "delayed_response",
        "duplicate_work_order",
        "lost_ack",
        "crash_after_actuation_before_receipt",
        "moving_subject",
        "concurrent_conflict",
        "failing_verifier",
        "flaky_verifier",
        "invalid_authority",
        "expired_credential",
        "generator_drift",
        "resource_pressure",
        "rate_limit",
        "dependency_outage",
        "impossible_objective",
        "silent_external_mutation",
        "long_horizon_multistage",
    }
    families = {s["family"] for s in manifest["scenarios"]}
    missing = required - families
    assert not missing, f"required fault families absent from corpus: {missing}"
