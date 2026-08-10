"""The concrete, falsifiable two-gym gate.

One generic sequence -- materialize -> observe (Observer) -> discover a real
DO capability -> actuate it (Actuator) under a real `AllowListAuthorityResolver`
-> verify (Verifier) -> teardown -- run through `gymact.runtime.GymAct` for two
mechanically different real providers:

  * `MemoryProvider` / `MemoryEnvironment` -- deterministic in-process dict world.
  * `GymnasiumProvider` / `GymnasiumEnvironment` -- real external `gymnasium`
    `CartPole-v1` physics environment (real `reset`, real numpy-derived state).

The test body below contains no provider-name branching whatsoever. The only
per-provider difference is the parametrize data: a provider factory, the
`materialize()` config, the capability IRI to actuate, the actuation payload,
an authority reference, and the expected postcondition dict handed to
`verify()`. If this passes identically for both rows, the same generic kernel
+ algebra path (`gymact.runtime.GymAct`, `gymact.algebra.Observer/Actuator/
Verifier`) genuinely works unchanged across two mechanically distinct real
worlds -- not just "importable," a real, evidenced, `solved`-free but
`verified=True` actuation with a real Receipt trail.

`KubernetesReconciliationProvider` was surveyed (see
`tests/test_algebra_protocols.py`) and confirmed real/runnable in source, but
no real cluster is reachable in this environment (`kubectl cluster-info` ->
TLS handshake timeout), so it is not one of the two rows here. The two rows
used are the two real, currently-runnable, mechanically-different providers
the survey confirmed: `memory` (in-process dict) and `gymnasium` (external
physics package).
"""

from __future__ import annotations

from typing import Any

import pytest

from gymact.algebra import Actuator, Observer, Verifier
from gymact.authority import AllowListAuthorityResolver
from gymact.gyms.gymnasium_env import GymnasiumProvider
from gymact.models import ActuationIntent, MaterializationIntent, Standing
from gymact.providers import MemoryProvider
from gymact.runtime import GymAct

_MEMORY_AUTHORITY_REF = "urn:gymact:test:authority:memory-set"
_GYMNASIUM_AUTHORITY_REF = "urn:gymact:test:authority:gymnasium-reset"

_CASES: tuple[tuple[str, Any, dict[str, Any], str, str, dict[str, Any], dict[str, Any]], ...] = (
    (
        "memory",
        MemoryProvider,
        {"requires_authority": True},
        "urn:gymact:memory:capability:set",
        _MEMORY_AUTHORITY_REF,
        {"key": "answer", "value": 42},
        {"answer": 42},
    ),
    (
        "gymnasium",
        GymnasiumProvider,
        {"env_id": "CartPole-v1", "requires_authority": True},
        "urn:gymact:gymnasium:capability:reset",
        _GYMNASIUM_AUTHORITY_REF,
        {},
        {"terminated": False, "truncated": False, "reward": None},
    ),
)


@pytest.mark.parametrize(
    "label,provider_factory,materialize_config,capability_iri,authority_ref,payload,expected",
    _CASES,
    ids=[case[0] for case in _CASES],
)
@pytest.mark.asyncio
async def test_two_gym_gate(
    label: str,
    provider_factory: Any,
    materialize_config: dict[str, Any],
    capability_iri: str,
    authority_ref: str,
    payload: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Same generic sequence, same generic assertions, zero provider branching.

    `label` is used only in an assertion message, never to select a code path.
    """
    del label

    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({authority_ref}))
    provider = provider_factory()
    kernel.register_provider(provider)

    # -- materialize --
    materialization = await kernel.materialize(
        MaterializationIntent(provider=provider.name, config=materialize_config)
    )
    assert materialization.accepted
    assert materialization.standing is Standing.ALIVE
    episode_id = materialization.episode.episode_id

    # -- observe (Observer contract) --
    observation = await kernel.observe(episode_id)
    assert isinstance(observation.state, dict)

    # -- discover at least 1 real DO capability, generically --
    capabilities = kernel.capabilities(episode_id)
    do_capabilities = {c.iri: c for c in capabilities if c.consequence.value == "DO"}
    assert do_capabilities, "provider exposed zero DO capabilities"
    assert capability_iri in do_capabilities, (
        f"parametrized capability {capability_iri!r} is not a real DO capability "
        f"this provider actually exposes: {sorted(do_capabilities)}"
    )
    capability = do_capabilities[capability_iri]

    # Structural proof: the materialized environment satisfies the narrower
    # Observer/Actuator/Verifier Protocols, same as `test_algebra_protocols.py`.
    environment = kernel._state(episode_id).environment  # real object, no adapter
    assert isinstance(environment, Observer)
    assert isinstance(environment, Actuator)
    assert isinstance(environment, Verifier)

    # -- actuate (Actuator contract) under a real AllowListAuthorityResolver --
    actuation = await kernel.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability.iri,
            payload=payload,
            authority_ref=authority_ref,
        )
    )
    assert actuation.accepted
    assert actuation.standing is Standing.ALIVE
    expected_evidence_ref = f"urn:gymact:authority-decision:{authority_ref}"
    assert actuation.receipt.authority_evidence_ref == expected_evidence_ref

    # -- verify (Verifier contract), independent of the actuator's own report --
    verification = await kernel.verify(episode_id, expected)
    assert verification.passed, f"expected {expected} but observed {verification.observed}"

    # -- teardown --
    teardown_receipt = await kernel.teardown(episode_id, authority_ref=authority_ref)
    assert teardown_receipt.standing is Standing.ALIVE

    # -- real Receipt trail, same generic shape, both providers --
    receipts = kernel.episode_receipts(episode_id)
    operations = [r.operation.value for r in receipts]
    assert operations == ["materialize", "act", "teardown"]
    assert all(r.episode_id == episode_id for r in receipts)
