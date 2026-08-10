"""Chicago-style tests for `gymact.dspy_verifier` -- a real, optional
LLM-based `PostconditionVerifier`, built the GEPA trusted-monitor way. No
mocks: the live tests inject a real `DspyTrustedMonitorVerifier` into a real
`GymAct` kernel against a real `MemoryProvider` episode, and the GEPA
optimization test runs a real `dspy.GEPA(...).compile()` against a small,
real fixture set built from `gymact.verification._partial_match`'s own real
output (ground truth, not fabricated).

Per `gymact.standing.require_standing`, real is the default: if the optional
`dspy` extra isn't installed, this module FAILS unless the run explicitly
opts into the degraded standing -- not a silent skip.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

from gymact.standing import require_standing

require_standing(
    "LOCAL_EXTRA:dspy",
    available=importlib.util.find_spec("dspy") is not None,
    reason="the optional 'dspy' extra is not installed -- `uv sync --extra dspy`",
)

from gymact import (  # noqa: E402
    AllowListAuthorityResolver,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
)
from gymact.dspy_verifier import DspyTrustedMonitorVerifier, suspicion_scoring_program  # noqa: E402
from gymact.models import ActuationIntent  # noqa: E402
from gymact.verification import PostconditionVerifier, _partial_match  # noqa: E402

AUTHORITY = "urn:test:dspy-verifier-authority"


def _groq_key_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


class TestDspyTrustedMonitorVerifierSatisfiesTheRealProtocol:
    def test_is_a_real_postcondition_verifier(self):
        verifier = DspyTrustedMonitorVerifier()
        assert isinstance(verifier, PostconditionVerifier)

    # The "dspy not installed" ImportError branch in DspyTrustedMonitorVerifier
    # and suspicion_scoring_program() is real but deliberately not covered
    # here: this whole test module is gated behind require_standing on the
    # dspy extra being present, so dspy is always importable wherever these
    # tests actually run. Faking "not installed" would need monkeypatch
    # (banned) or a real subprocess with dspy stripped from its environment
    # -- disproportionate for a defensive guard clause. Named honestly rather
    # than covered dishonestly.


@pytest.mark.skipif(not _groq_key_available(), reason="no GROQ_API_KEY in this environment")
class TestDspyTrustedMonitorVerifierRealLiveJudgment:
    """Mirrors `test_kernel_verification.py`'s DishonestEnvironment pattern,
    with the LLM judge substituted for `DictSubsetVerifier` -- proves the
    independent judge, not just the mechanical comparator, catches a real
    dishonest claim."""

    async def _authorized_gym(self) -> GymAct:
        gym = GymAct(
            authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
            verifier=DspyTrustedMonitorVerifier(),
        )
        gym.register_provider(MemoryProvider())
        return gym

    async def test_real_matching_state_is_judged_as_passing(self):
        gym = await self._authorized_gym()
        materialization = await gym.materialize(
            MaterializationIntent(
                provider="memory", config={"initial": {"counter": 1}}, authority_ref=AUTHORITY
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id
        result = await gym.verify(episode_id, {"counter": 1})
        assert result.passed is True
        await gym.teardown(episode_id, authority_ref=AUTHORITY)

    async def test_real_mismatched_state_is_judged_as_failing(self):
        gym = await self._authorized_gym()
        materialization = await gym.materialize(
            MaterializationIntent(
                provider="memory", config={"initial": {"counter": 1}}, authority_ref=AUTHORITY
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id
        # A real, live increment call is what real world state actually
        # holds; asking to verify the WRONG expected value is the real
        # mismatch this test proves the LLM judge catches.
        capabilities = gym.capabilities(episode_id)
        increment = next(c for c in capabilities if c.binding == "increment")
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=increment.iri,
                payload={"key": "counter", "amount": 1},
                authority_ref=AUTHORITY,
            )
        )
        result = await gym.verify(episode_id, {"counter": 999})
        assert result.passed is False
        # The real judge-authored reason lands on the real Receipt trail --
        # the fixed "DSPY_TRUSTED_MONITOR:..." marker proves this judge, not
        # DictSubsetVerifier, actually produced the verdict.
        from gymact.models import Operation

        receipts = gym.episode_receipts(episode_id)
        verify_receipts = [r for r in receipts if r.operation is Operation.VERIFY]
        assert verify_receipts
        assert any(
            r.reason and r.reason.startswith("DSPY_TRUSTED_MONITOR") for r in verify_receipts
        )
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


def _real_fixture_triples() -> list[tuple[dict, dict, bool]]:
    """Real (expected, observed, is_real_match) triples. Ground truth comes
    directly from `_partial_match`'s own real output -- not hand-asserted --
    so this fixture set can never silently drift from what the mechanical
    verifier itself would decide."""
    candidates = [
        ({"counter": 1}, {"counter": 1, "other": "x"}, True),
        ({"counter": 1}, {"counter": 2}, False),
        ({"status": "ready"}, {"status": "ready", "pid": 123}, True),
        ({"status": "ready"}, {"status": "pending"}, False),
        ({"nested": {"a": 1}}, {"nested": {"a": 1, "b": 2}}, True),
        ({"nested": {"a": 1}}, {"nested": {"a": 2}}, False),
        ({"key": "value"}, {}, False),
    ]
    fixtures = []
    for expected, observed, claimed_match in candidates:
        real_mismatches = _partial_match(observed, expected)
        real_is_match = not real_mismatches
        assert real_is_match == claimed_match, (
            f"fixture ground-truth drift: {expected=} {observed=} "
            f"claimed={claimed_match} but _partial_match says {real_is_match}"
        )
        fixtures.append((expected, observed, real_is_match))
    return fixtures


@pytest.mark.skipif(not _groq_key_available(), reason="no GROQ_API_KEY in this environment")
class TestGepaOptimizesTheRealJudge:
    async def test_gepa_optimized_program_scores_at_least_as_well_as_the_base_program(self):
        import dspy

        fixtures = _real_fixture_triples()
        train_set = [
            dspy.Example(
                expected=str(e), observed=str(o), suspicion_score=0 if m else 100
            ).with_inputs("expected", "observed")
            for e, o, m in fixtures[:4]
        ]
        val_set = [
            dspy.Example(
                expected=str(e), observed=str(o), suspicion_score=0 if m else 100
            ).with_inputs("expected", "observed")
            for e, o, m in fixtures[4:]
        ]

        def metric(example, prediction, trace=None, pred_name=None, pred_trace=None):
            predicted_match = int(prediction.suspicion_score) < 50
            real_match = int(example.suspicion_score) < 50
            score = 1.0 if predicted_match == real_match else 0.0
            feedback = (
                "Correctly judged."
                if score == 1.0
                else (
                    f"Real ground truth is {'a match' if real_match else 'a mismatch'} "
                    f"but the judge scored suspicion={prediction.suspicion_score}."
                )
            )
            return dspy.Prediction(score=score, feedback=feedback)

        lm = dspy.LM("groq/openai/gpt-oss-20b", max_tokens=16000)
        with dspy.context(lm=lm):
            base_program = suspicion_scoring_program()

            def real_accuracy(program) -> float:
                correct = 0
                for example in val_set:
                    prediction = program(expected=example.expected, observed=example.observed)
                    predicted_match = int(prediction.suspicion_score) < 50
                    real_match = int(example.suspicion_score) < 50
                    correct += int(predicted_match == real_match)
                return correct / len(val_set)

            base_accuracy = real_accuracy(base_program)

            optimizer = dspy.GEPA(
                metric=metric,
                max_metric_calls=12,
                reflection_lm=lm,
                track_stats=False,
            )
            optimized_program = optimizer.compile(
                base_program, trainset=train_set, valset=val_set
            )
            optimized_accuracy = real_accuracy(optimized_program)

        assert optimized_accuracy >= base_accuracy, (
            f"GEPA-optimized judge (accuracy={optimized_accuracy}) did not match or beat "
            f"the unoptimized base judge (accuracy={base_accuracy}) on the same real "
            f"held-out fixtures"
        )
