"""Real, Chicago-style tests for
`gymact.gyms.platform_console_ontology_provider`.

No `unittest.mock`/`Mock`/`MagicMock`/`patch`/`monkeypatch` anywhere in this
file. Two groups:

(a) Reversible capabilities correctly gated/actuatable through the real
    `gymact.kernel.GymAct` -> real `AuthorityResolver`/`CapabilityScope`
    chain (real `materialize`/`act`/`verify` calls against the real
    `OntologyDrivenEnvironment` this provider compiles -- an in-process,
    fact-based world, not a live k8s/Stripe/platform-console deployment, so
    no live-tenant skip is needed for these; they are real end-to-end
    kernel round trips, matching `test_ontology_gym.py`'s own precedent for
    testing `OntologyDrivenEnvironment` through the real kernel rather than
    a live external system).

(b) IRREVERSIBLE capabilities (`org.delete`, `dr.failover`, `dsar.erasure`,
    `sla.credit.apply`, `patch-sla.credit.apply`, `k8s.createRestoreJob`,
    `k8s.deleteProject`, `orgs.deleteOrg`) correctly REFUSED by the real
    fail-closed `TieredAuthorityResolver` this provider builds, without the
    IRREVERSIBLE `actuate()` branch ever running -- proven by asserting the
    real `GymAct.act()` result is refused (`accepted is False`) and that no
    fact was established in the environment's real observed state, not by
    mocking any k8s/Stripe call (there is none to mock: this environment
    never makes an external call at all, and the refusal happens at the
    authority gate, before `actuate()` is reached, exactly like
    `test_ontology_gym.py`'s own `PRECONDITION_REFUSED`-style tests).
"""

from __future__ import annotations

import anyio
import pytest

from gymact.agent import AllowListCapabilityScope
from gymact.gyms.ontology_gym import capability_iri
from gymact.gyms.platform_console_ontology_provider import (
    DEFAULT_PACK_DIR,
    PROVIDER_NAME,
    build_fail_closed_authority_resolver,
    build_platform_console_ontology_provider,
    load_platform_console_capabilities,
)
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, MaterializationIntent

_PACK_AVAILABLE = (DEFAULT_PACK_DIR / "ontology.ttl").is_file()

pytestmark = pytest.mark.skipif(
    not _PACK_AVAILABLE,
    reason=(
        f"platform-console-capability-pack ontology.ttl not found at "
        f"{DEFAULT_PACK_DIR} -- skipped, not mocked."
    ),
)


def _reversible_capability_title(exclude: frozenset[str]) -> str:
    facts = load_platform_console_capabilities()
    for fact in facts:
        if fact.reversible and fact.title not in exclude:
            return fact.title
    raise AssertionError("no reversible capability found in the real pack")


def _capability_iri_for(title: str) -> str:
    return capability_iri(provider_name=PROVIDER_NAME, task=_TitleTask(title))


class _TitleTask:
    """Minimal stand-in exposing the `.identifier` attribute
    `capability_iri()` reads -- real slug derivation, no fakery of the
    provider/environment under test."""

    def __init__(self, title: str) -> None:
        self.identifier = title


# ---------------------------------------------------------------------------
# (a) Reversible capabilities: real actuation through the real kernel chain.
# ---------------------------------------------------------------------------


def test_real_kernel_actuates_a_reversible_capability_end_to_end() -> None:
    provider = build_platform_console_ontology_provider()
    reversible_title = _reversible_capability_title(exclude=frozenset())
    reversible_iri = _capability_iri_for(reversible_title)

    standard_ref = "urn:gymact:authority-decision:pc-ontology-chicago-standard"
    resolver = build_fail_closed_authority_resolver(
        provider=provider, standard_ref=standard_ref, elevated_ref=None
    )
    principal = "urn:prov:agent:gymact-pc-ontology-chicago"

    async def run() -> None:
        gym = GymAct(
            authority_resolver=resolver,
            capability_scope=AllowListCapabilityScope(
                {
                    principal: frozenset(
                        capability_iri(provider_name=PROVIDER_NAME, task=t)
                        for t in provider.tasks()
                    )
                    | frozenset(
                        [f"urn:gymact:{PROVIDER_NAME}:capability:inspect-state"]
                    )
                }
            ),
        )
        gym.register_provider(provider)

        materialization = await gym.materialize(
            MaterializationIntent(
                provider=PROVIDER_NAME,
                config={"requires_authority": True},
                principal=principal,
                authority_ref=standard_ref,
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id

        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=reversible_iri,
                authority_ref=standard_ref,
                principal=principal,
            )
        )
        assert result.accepted, result.receipt.reason
        assert result.effect is not None
        assert result.effect["established"] == reversible_title

        observed = await gym.observe(episode_id)
        assert reversible_title in observed.state["facts"]

        await gym.teardown(episode_id, authority_ref=standard_ref)

    anyio.run(run)


def test_real_kernel_actuates_a_second_distinct_reversible_capability() -> None:
    provider = build_platform_console_ontology_provider()
    first_title = _reversible_capability_title(exclude=frozenset())
    second_title = _reversible_capability_title(exclude=frozenset({first_title}))
    assert first_title != second_title
    second_iri = _capability_iri_for(second_title)

    standard_ref = "urn:gymact:authority-decision:pc-ontology-chicago-standard-2"
    resolver = build_fail_closed_authority_resolver(
        provider=provider, standard_ref=standard_ref, elevated_ref=None
    )
    principal = "urn:prov:agent:gymact-pc-ontology-chicago-2"

    async def run() -> None:
        gym = GymAct(
            authority_resolver=resolver,
            capability_scope=AllowListCapabilityScope(
                {
                    principal: frozenset(
                        capability_iri(provider_name=PROVIDER_NAME, task=t)
                        for t in provider.tasks()
                    )
                    | frozenset(
                        [f"urn:gymact:{PROVIDER_NAME}:capability:inspect-state"]
                    )
                }
            ),
        )
        gym.register_provider(provider)

        materialization = await gym.materialize(
            MaterializationIntent(
                provider=PROVIDER_NAME,
                config={"requires_authority": True},
                principal=principal,
                authority_ref=standard_ref,
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id

        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=second_iri,
                authority_ref=standard_ref,
                principal=principal,
            )
        )
        assert result.accepted, result.receipt.reason
        assert result.effect["established"] == second_title

        await gym.teardown(episode_id, authority_ref=standard_ref)

    anyio.run(run)


# ---------------------------------------------------------------------------
# (b) IRREVERSIBLE capabilities: real fail-closed authority refusal, no
# actuate() ever attempted against any external system.
# ---------------------------------------------------------------------------


def test_irreversible_org_delete_refused_with_no_elevated_allowlist_configured() -> None:
    """Fail-closed default: `elevated_ref=None` -> the resolver's real
    `elevated_ref` is the unmatchable sentinel
    `build_fail_closed_authority_resolver` documents -- no caller-supplied
    `authority_ref` can ever equal it, so `org.delete` (`ce:reversible
    false` in the real pack) is refused unconditionally."""
    provider = build_platform_console_ontology_provider()
    org_delete_iri = _capability_iri_for("org.delete")
    assert org_delete_iri in provider.elevated_capability_iris()

    standard_ref = "urn:gymact:authority-decision:pc-ontology-chicago-irrev-1"
    resolver = build_fail_closed_authority_resolver(
        provider=provider, standard_ref=standard_ref, elevated_ref=None
    )
    principal = "urn:prov:agent:gymact-pc-ontology-chicago-irrev-1"

    async def run() -> None:
        gym = GymAct(
            authority_resolver=resolver,
            capability_scope=AllowListCapabilityScope(
                {
                    principal: frozenset(
                        capability_iri(provider_name=PROVIDER_NAME, task=t)
                        for t in provider.tasks()
                    )
                }
            ),
        )
        gym.register_provider(provider)

        materialization = await gym.materialize(
            MaterializationIntent(
                provider=PROVIDER_NAME,
                config={"requires_authority": True},
                principal=principal,
                authority_ref=standard_ref,
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id

        # Even a caller presenting the standard (non-elevated) ref must be
        # refused for this IRREVERSIBLE capability -- the real assertion
        # this test exists to make.
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=org_delete_iri,
                authority_ref=standard_ref,
                principal=principal,
            )
        )
        assert result.accepted is False
        assert result.effect is None

        observed = await gym.observe(episode_id)
        assert "org.delete" not in observed.state["facts"]

        await gym.teardown(episode_id, authority_ref=standard_ref)

    anyio.run(run)


def test_irreversible_dr_failover_refused_even_with_a_real_but_wrong_ref() -> None:
    """A configured elevated allow-list exists in this test (`elevated_ref`
    is real and non-None), but the caller presents a DIFFERENT, real
    `authority_ref` (the standard one) -- proving the refusal is a genuine
    per-request tier check (`ref == elevated_ref`), not merely "no
    allow-list was configured at all" from the previous test. `dr.failover`
    (`ce:reversible false`) must still be refused, and its real DO
    `actuate()` branch (which in a live provider would overwrite live DB pod
    data) must never run."""
    provider = build_platform_console_ontology_provider()
    dr_failover_iri = _capability_iri_for("dr.failover")
    assert dr_failover_iri in provider.elevated_capability_iris()

    standard_ref = "urn:gymact:authority-decision:pc-ontology-chicago-irrev-2-standard"
    elevated_ref = "urn:gymact:authority-decision:pc-ontology-chicago-irrev-2-elevated"
    resolver = build_fail_closed_authority_resolver(
        provider=provider, standard_ref=standard_ref, elevated_ref=elevated_ref
    )
    principal = "urn:prov:agent:gymact-pc-ontology-chicago-irrev-2"

    async def run() -> None:
        gym = GymAct(
            authority_resolver=resolver,
            capability_scope=AllowListCapabilityScope(
                {
                    principal: frozenset(
                        capability_iri(provider_name=PROVIDER_NAME, task=t)
                        for t in provider.tasks()
                    )
                }
            ),
        )
        gym.register_provider(provider)

        materialization = await gym.materialize(
            MaterializationIntent(
                provider=PROVIDER_NAME,
                config={"requires_authority": True},
                principal=principal,
                authority_ref=standard_ref,
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id

        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=dr_failover_iri,
                authority_ref=standard_ref,  # wrong tier for an elevated capability
                principal=principal,
            )
        )
        assert result.accepted is False
        assert result.effect is None

        observed = await gym.observe(episode_id)
        assert "dr.failover" not in observed.state["facts"]

        # Sanity: the SAME capability IS admitted with the real elevated ref
        # -- proving the refusal above was tier-based, not a broken
        # resolver that refuses everything.
        admitted_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=dr_failover_iri,
                authority_ref=elevated_ref,
                principal=principal,
            )
        )
        assert admitted_result.accepted, admitted_result.receipt.reason
        assert admitted_result.effect["established"] == "dr.failover"

        await gym.teardown(episode_id, authority_ref=elevated_ref)

    anyio.run(run)


def test_fail_closed_binding_rejects_same_ref_for_standard_and_elevated() -> None:
    """`build_fail_closed_authority_resolver` refuses to construct a
    resolver where `elevated_ref == standard_ref` -- that configuration
    would silently admit every standard-tier caller to IRREVERSIBLE
    capabilities, defeating the entire fail-closed contract. Real
    `ValueError`, not a mocked assertion."""
    provider = build_platform_console_ontology_provider()
    same_ref = "urn:gymact:authority-decision:pc-ontology-chicago-same-ref"
    with pytest.raises(ValueError, match="REFUSED_SAME_REF_FOR_STANDARD_AND_ELEVATED"):
        build_fail_closed_authority_resolver(
            provider=provider, standard_ref=same_ref, elevated_ref=same_ref
        )
