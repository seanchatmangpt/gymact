"""Real (no mocks) proof that `GymAct.verify()` no longer trusts a
provider's own self-reported verdict.

Per `.claude/rules/testing-chicago-style.md`'s own carve-out, a hand-written,
simple, real implementation of a Protocol (here: a real `Environment` whose
`verify()` always claims success regardless of `expected`) is not a mock --
it is a real object with real, if dishonest, behavior. That is exactly what
this module needs: a real collaborator that lies, to prove the independent
judge (`gymact.verification.PostconditionVerifier`) catches it -- not an
`unittest.mock`/`Mock`/`patch`/`monkeypatch` standing in for one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gymact import (
    Capability,
    Consequence,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
    Operation,
)
from gymact.verification import DictSubsetVerifier, PostconditionVerifier

DISHONEST_SET = Capability(
    iri="urn:test:dishonest:capability:set",
    title="Set a value, but verify() always claims success regardless of what was asked",
    consequence=Consequence.DO,
    binding="set",
)


@dataclass
class DishonestEnvironment:
    """A real, hand-written `Environment` whose `verify()` unconditionally
    reports success, ignoring `expected` entirely -- the exact dishonest
    provider shape `gymact.verification`'s module docstring describes."""

    environment_id: str = "urn:test:dishonest:environment:1"
    requires_authority: bool = False
    _state: dict[str, Any] = field(default_factory=dict)

    def capabilities(self) -> tuple[Capability, ...]:
        return (DISHONEST_SET,)

    async def observe(self) -> dict[str, Any]:
        return dict(self._state)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del capability
        self._state[payload["key"]] = payload["value"]
        return {"accepted": True}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        del expected  # a dishonest provider ignoring what was actually asked
        return True, dict(self._state)

    async def checkpoint(self) -> dict[str, Any]:
        return dict(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._state = dict(checkpoint)

    async def teardown(self) -> None:
        pass


class DishonestProvider:
    name = "dishonest"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> DishonestEnvironment:
        del scenario, config
        return DishonestEnvironment()


class AlwaysFailVerifier:
    """A real, non-default `PostconditionVerifier` -- proves the injection
    point is genuinely used, not hardwired to `DictSubsetVerifier`."""

    def judge(self, expected: dict[str, Any], observed: dict[str, Any]) -> tuple[bool, str]:
        del expected, observed
        return False, "ALWAYS_FAIL_TEST_VERIFIER"


async def test_default_verifier_catches_a_dishonest_providers_false_success_claim() -> None:
    gym = GymAct()
    gym.register_provider(DishonestProvider())
    materialization = await gym.materialize(MaterializationIntent(provider="dishonest", config={}))
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    from gymact.models import ActuationIntent

    await gym.act(
        ActuationIntent(
            episode_id=episode_id, capability=DISHONEST_SET.iri, payload={"key": "x", "value": 1}
        )
    )

    # The provider's own verify() would happily claim this passed (it ignores
    # `expected` entirely) -- but x is really 1, not 999, so the independent
    # judge must catch it.
    result = await gym.verify(episode_id, {"x": 999})
    assert result.passed is False, "independent verifier was fooled by the dishonest provider"

    receipts = gym.episode_receipts(episode_id)
    verify_receipts = [r for r in receipts if r.operation is Operation.VERIFY]
    assert len(verify_receipts) == 1
    receipt = verify_receipts[0]
    assert receipt.verified is False
    assert "PROVIDER_VERIFY_DIVERGENCE:provider_reported=True" in receipt.reason
    assert "VERIFY_MISMATCH:x" in receipt.reason


async def test_honest_memory_provider_agrees_and_emits_a_real_verify_receipt() -> None:
    gym = GymAct()
    gym.register_provider(MemoryProvider())
    materialization = await gym.materialize(
        MaterializationIntent(provider="memory", config={"initial": {"count": 1}})
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    result = await gym.verify(episode_id, {"count": 1})
    assert result.passed is True

    receipts = gym.episode_receipts(episode_id)
    verify_receipts = [r for r in receipts if r.operation is Operation.VERIFY]
    assert len(verify_receipts) == 1
    receipt = verify_receipts[0]
    assert receipt.verified is True
    assert "PROVIDER_VERIFY_DIVERGENCE" not in receipt.reason
    assert receipt.reason == "VERIFIED:SUBSET_MATCH"

    ocel_log = gym.episode_ocel_log(episode_id)
    verify_events = [e for e in ocel_log["events"] if e["type"] == "verify"]
    assert len(verify_events) == 1, (
        "no gym's real verify() previously produced an OCEL event at all"
    )


async def test_a_custom_injected_verifier_is_genuinely_used_instead_of_the_default() -> None:
    gym = GymAct(verifier=AlwaysFailVerifier())
    gym.register_provider(MemoryProvider())
    materialization = await gym.materialize(
        MaterializationIntent(provider="memory", config={"initial": {"count": 1}})
    )
    episode_id = materialization.episode.episode_id

    # A trivially-true expectation that DictSubsetVerifier would pass --
    # proves AlwaysFailVerifier, not the default, is what actually ran.
    result = await gym.verify(episode_id, {"count": 1})
    assert result.passed is False

    receipts = gym.episode_receipts(episode_id)
    verify_receipt = next(r for r in receipts if r.operation is Operation.VERIFY)
    assert (
        verify_receipt.reason
        == "ALWAYS_FAIL_TEST_VERIFIER;PROVIDER_VERIFY_DIVERGENCE:provider_reported=True"
    )


def test_dict_subset_verifier_matches_local_providers_partial_match_semantics() -> None:
    """Real, Docker-free unit coverage of the pure comparator logic itself."""
    verifier: PostconditionVerifier = DictSubsetVerifier()

    passed, reason = verifier.judge(
        {"files": {"proof.txt": {"size": 5}}},
        {"files": {"proof.txt": {"size": 5, "sha256": "unrelated-extra-key"}}},
    )
    assert passed is True
    assert reason == "VERIFIED:SUBSET_MATCH"

    passed, reason = verifier.judge(
        {"files": {"proof.txt": {"size": 5}}},
        {"files": {"proof.txt": {"size": 999}}},
    )
    assert passed is False
    assert reason == "VERIFY_MISMATCH:files.proof.txt.size"

    passed, reason = verifier.judge({"missing_key": 1}, {})
    assert passed is False
    assert reason == "VERIFY_MISMATCH:missing_key"
