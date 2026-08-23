"""Proves `gymact.algebra`'s Observer/Actuator/Verifier Protocols are
satisfied automatically, via Python structural typing, by real
`Environment` implementations -- zero adapter code, zero gym-specific
code in `algebra.py` itself.

Two mechanically-different real providers are used, both confirmed
real/runnable in this repo's environment (Chicago style: real objects,
real state, no mocks):

  * `MemoryProvider` / `MemoryEnvironment` -- a real deterministic
    in-process dict-backed world (`gymact/providers.py`).
  * `GymnasiumProvider` / `GymnasiumEnvironment` -- a real external
    `gymnasium` package's `CartPole-v1` physics environment
    (`gymact/gyms/gymnasium_env.py`), a mechanically distinct kind of
    world (real physics step/reset loop, real numpy-derived state)
    from the memory world.

`KubernetesReconciliationEnvironment` (`gymact/gyms/kubernetes_reconciliation.py`)
would be a third real, mechanically-different provider (real
`kubectl`/cluster-backed world) but is skipped here via
`gymact.standing.require_standing` because no real cluster is reachable
in this run (`kubectl cluster-info` fails with a TLS handshake timeout) --
a named, visible skip, never a silent mock substitution.
"""

from __future__ import annotations

import subprocess

import pytest

from gymact.algebra import Actuator, Observer, Verifier
from gymact.gyms.gymnasium_env import GymnasiumEnvironment, GymnasiumProvider
from gymact.gyms.kubernetes_reconciliation import (
    KubernetesReconciliationEnvironment,
    KubernetesReconciliationProvider,
)
from gymact.models import Capability, Consequence
from gymact.providers import Environment, MemoryEnvironment, MemoryProvider
from gymact.standing import require_standing


def _kubernetes_cluster_reachable() -> bool:
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _declared_protocol_methods(protocol: type[object]) -> set[str]:
    """Return public callable members declared directly on a Protocol.

    ``typing.Protocol.__protocol_attrs__`` is a private CPython implementation
    detail and is not portable across the supported Python matrix.  Inspecting
    the Protocol class namespace proves the same source-level contract without
    depending on a private runtime attribute.
    """
    return {
        name
        for name, value in vars(protocol).items()
        if not name.startswith("_") and callable(value)
    }


@pytest.mark.asyncio
async def test_memory_environment_satisfies_environment_protocol() -> None:
    provider = MemoryProvider()
    environment = await provider.materialize(scenario=None, config={})
    assert isinstance(environment, Environment)


@pytest.mark.asyncio
async def test_memory_environment_satisfies_observer_actuator_verifier() -> None:
    provider = MemoryProvider()
    environment: MemoryEnvironment = await provider.materialize(scenario=None, config={})
    try:
        assert isinstance(environment, Observer)
        assert isinstance(environment, Actuator)
        assert isinstance(environment, Verifier)

        observer: Observer = environment
        actuator: Actuator = environment
        verifier: Verifier = environment

        capabilities = observer.capabilities()
        assert len(capabilities) > 0
        before = await observer.observe()
        assert before == {}

        set_capability = next(c for c in capabilities if c.binding == "set")
        result = await actuator.actuate(set_capability, {"key": "x", "value": 1})
        assert result["after"] == {"x": 1}

        passed, observed = await verifier.verify({"x": 1})
        assert passed is True
        assert observed == {"x": 1}
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_gymnasium_environment_satisfies_environment_protocol() -> None:
    provider = GymnasiumProvider()
    environment = await provider.materialize(
        scenario=None, config={"env_id": "CartPole-v1", "requires_authority": False}
    )
    try:
        assert isinstance(environment, Environment)
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_gymnasium_environment_satisfies_observer_actuator_verifier() -> None:
    provider = GymnasiumProvider()
    environment: GymnasiumEnvironment = await provider.materialize(
        scenario=None, config={"env_id": "CartPole-v1", "requires_authority": False}
    )
    try:
        assert isinstance(environment, Observer)
        assert isinstance(environment, Actuator)
        assert isinstance(environment, Verifier)

        observer: Observer = environment
        actuator: Actuator = environment
        verifier: Verifier = environment

        capabilities = observer.capabilities()
        assert any(c.binding == "step" for c in capabilities)
        before = await observer.observe()
        assert before["env_id"] == "CartPole-v1"

        sample_capability = next(c for c in capabilities if c.binding == "sample_action")
        sampled = await actuator.actuate(sample_capability, {})
        action = sampled["action"]

        step_capability = next(c for c in capabilities if c.binding == "step")
        stepped = await actuator.actuate(step_capability, {"action": action})
        assert "after" in stepped

        passed, observed = await verifier.verify({"env_id": "CartPole-v1"})
        assert passed is True
        assert observed["env_id"] == "CartPole-v1"
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_kubernetes_reconciliation_environment_satisfies_observer_actuator_verifier() -> (
    None
):
    reachable = _kubernetes_cluster_reachable()
    require_standing(
        "PARTIAL_ALIVE",
        available=reachable,
        reason=(
            "no reachable Kubernetes cluster for kubectl cluster-info "
            "(set GYMACT_ALLOW_DEGRADED_STANDINGS=PARTIAL_ALIVE to skip explicitly)"
        ),
    )
    if not reachable:
        pytest.skip("no reachable Kubernetes cluster (see require_standing reason above)")

    provider = KubernetesReconciliationProvider()
    environment: KubernetesReconciliationEnvironment = await provider.materialize(
        scenario=None, config={"requires_authority": False}
    )
    try:
        assert isinstance(environment, Environment)
        assert isinstance(environment, Observer)
        assert isinstance(environment, Actuator)
        assert isinstance(environment, Verifier)
    finally:
        await environment.teardown()


def test_algebra_protocols_declare_only_the_matching_environment_methods() -> None:
    """Protocol views are exactly the matching Environment method subsets."""
    assert _declared_protocol_methods(Observer) == {"capabilities", "observe"}
    assert _declared_protocol_methods(Actuator) == {"actuate"}
    assert _declared_protocol_methods(Verifier) == {"verify"}


def test_capability_import_unused_placeholder() -> None:
    capability = Capability(
        iri="urn:gymact:test:capability:noop",
        title="noop",
        consequence=Consequence.READ,
        binding="noop",
    )
    assert capability.binding == "noop"
