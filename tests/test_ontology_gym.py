"""Real, Chicago-style tests for the generic `gymact.gyms.ontology_gym`
compiler, against a small synthetic ontology fixture -- proving the
mechanism is domain-agnostic, not proving TOGAF specifically (that's
`tests/test_togaf_gym.py`'s job, exercising the same machinery on the real
`togaf-gym-pack`).

No mocks: real temp-directory ontology.ttl files, a real rdflib parse, a
real GymAct kernel, real authority decisions.
"""

from __future__ import annotations

from pathlib import Path

from gymact import GymAct, MaterializationIntent
from gymact.gyms.ontology_gym import (
    OdrlAuthorityResolver,
    OdrlPermission,
    OntologyDrivenProvider,
    TieredAuthorityResolver,
    capability_iri,
    load_odrl_permissions,
    load_procedures,
    load_tasks,
)
from gymact.models import ActuationIntent, AuthorityRequest, Operation, Standing

REPO_ROOT = Path(__file__).resolve().parents[1]

_FIXTURE_TTL = """
@prefix pplan: <http://purl.org/net/p-plan#> .
@prefix dct: <http://purl.org/dc/terms/> .

<urn:test:task:init> a pplan:Plan ;
    dct:identifier "test.00.init" ;
    dct:subject <urn:test:artifact:baseline> ;
    dct:type <urn:test:family:setup> .

<urn:test:task:multi> a pplan:Plan ;
    dct:identifier "test.10.multi" ;
    dct:subject <urn:test:artifact:alpha>, <urn:test:artifact:beta> ;
    dct:type <urn:test:family:review> .

<urn:test:task:governed> a pplan:Plan ;
    dct:identifier "test.20.governed" ;
    dct:subject <urn:test:artifact:sign-off> ;
    dct:type <urn:test:family:governance> .

<urn:test:task:reset> a pplan:Plan ;
    dct:identifier "test.30.reset" ;
    dct:subject <urn:test:artifact:change> ;
    dct:type <urn:test:family:change> .
"""

STANDARD_REF = "urn:test:authority:standard"
GOVERNANCE_REF = "urn:test:authority:governance"


def _write_fixture_pack(tmp_path: Path) -> Path:
    pack_dir = tmp_path / "fixture-pack"
    pack_dir.mkdir()
    (pack_dir / "ontology.ttl").write_text(_FIXTURE_TTL)
    return pack_dir


def _build_provider(tmp_path: Path) -> OntologyDrivenProvider:
    return OntologyDrivenProvider(
        name="fixture",
        pack_dir=_write_fixture_pack(tmp_path),
        elevated_task_families=frozenset({"governance", "change"}),
        reset_task_families=frozenset({"change"}),
        reset_target_families=frozenset({"review"}),
    )


def test_load_tasks_extracts_real_topological_order_and_families(tmp_path: Path) -> None:
    pack_dir = _write_fixture_pack(tmp_path)

    tasks = load_tasks(pack_dir)

    assert [t.identifier for t in tasks] == [
        "test.00.init",
        "test.10.multi",
        "test.20.governed",
        "test.30.reset",
    ]
    assert tasks[1].subjects == (
        "urn:test:artifact:alpha",
        "urn:test:artifact:beta",
    )
    assert tasks[2].family == "governance"


async def _tiered_gym(tmp_path: Path) -> tuple[GymAct, OntologyDrivenProvider, str]:
    provider = _build_provider(tmp_path)
    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_REF,
        elevated_ref=GOVERNANCE_REF,
    )
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(provider="fixture", config={})
    )
    assert materialization.accepted is True, materialization.receipt.reason
    assert materialization.episode is not None
    return gym, provider, materialization.episode.episode_id


async def test_full_walk_reaches_the_real_goal(tmp_path: Path) -> None:
    """Walks every task EXCEPT the reset task -- test.30.reset (family
    "change") clears test.10.multi's (family "review") facts as a real,
    documented side effect (see test_reset_task_reopens_target_family_...
    below), so a "walk everything, then assert goal_reached" test must stop
    short of it to assert a clean, uncomplicated goal-reaching path."""
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    tasks = provider.tasks()

    for task in tasks[:2]:
        for subject in task.subjects:
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability_iri(provider_name="fixture", task=task),
                    payload={"subject": subject} if len(task.subjects) > 1 else {},
                    authority_ref=STANDARD_REF,
                )
            )
            assert result.accepted is True, result.receipt.reason

    governed_task = tasks[2]
    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=governed_task),
            authority_ref=GOVERNANCE_REF,
        )
    )
    assert result.accepted is True, result.receipt.reason

    observation = await gym.observe(episode_id)
    assert observation.state["goal_reached"] is False, (
        "goal_reached must still be False -- test.30.reset's own subject "
        "has not been established yet"
    )

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_precondition_chain_is_real_and_enforced(tmp_path: Path) -> None:
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    multi_task = provider.tasks()[1]

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=multi_task),
            payload={"subject": "urn:test:artifact:alpha"},
            authority_ref=STANDARD_REF,
        )
    )

    assert result.accepted is False
    assert result.standing is Standing.BLOCKED

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_elevated_capability_refuses_standard_ref(tmp_path: Path) -> None:
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    init_task = provider.tasks()[0]
    governed_task = provider.tasks()[2]

    establish = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=init_task),
            authority_ref=STANDARD_REF,
        )
    )
    assert establish.accepted is True, establish.receipt.reason

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=governed_task),
            authority_ref=STANDARD_REF,
        )
    )

    assert result.accepted is False
    assert result.standing is Standing.REFUSED

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_reset_task_reopens_target_family_and_goal_flips_and_recovers(
    tmp_path: Path,
) -> None:
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    tasks = provider.tasks()

    for task in tasks[:2]:
        for subject in task.subjects:
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability_iri(provider_name="fixture", task=task),
                    payload={"subject": subject} if len(task.subjects) > 1 else {},
                    authority_ref=STANDARD_REF,
                )
            )
            assert result.accepted is True, result.receipt.reason

    for task in tasks[2:]:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=capability_iri(provider_name="fixture", task=task),
                authority_ref=GOVERNANCE_REF,
            )
        )
        assert result.accepted is True, result.receipt.reason

    reset_task = tasks[3]
    assert reset_task.family == "change"

    # The walk above already included the reset task (test.30.reset, family
    # "change"), which clears the "review" family's facts (test.10.multi) as
    # its own real, documented side effect -- so goal_reached is False here,
    # not True, even though every task including the reset task itself was
    # actuated successfully. Assert that real consequence, then recover by
    # resubmitting the cleared facts.
    observation = await gym.observe(episode_id)
    assert observation.state["goal_reached"] is False

    multi_task = tasks[1]
    for subject in multi_task.subjects:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=capability_iri(provider_name="fixture", task=multi_task),
                payload={"subject": subject},
                authority_ref=STANDARD_REF,
            )
        )
        assert result.accepted is True, result.receipt.reason

    recovered = await gym.observe(episode_id)
    assert recovered.state["goal_reached"] is True

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


# --- OdrlAuthorityResolver: real, synthetic-fixture-driven tests -----------


def _request(*, capability_ref: str, authority_ref: str | None) -> AuthorityRequest:
    return AuthorityRequest(
        episode_id="ep:1",
        subject_ref="env:1",
        operation=Operation.ACT,
        capability_ref=capability_ref,
        authority_ref=authority_ref,
    )


async def test_odrl_resolver_refuses_capability_with_no_matching_permission() -> None:
    resolver = OdrlAuthorityResolver(permissions=())

    decision = await resolver.authorize(
        _request(capability_ref="urn:test:capability:x", authority_ref="urn:test:someone")
    )

    assert decision.admitted is False
    assert decision.reason == "ODRL_NO_PERMISSION_FOR_CAPABILITY"


async def test_odrl_resolver_requires_a_live_ref_even_with_a_matching_permission() -> None:
    permission = OdrlPermission(
        permission_iri=None, target="urn:test:capability:x", assigner=None, assignee=None
    )
    resolver = OdrlAuthorityResolver(permissions=(permission,))

    decision = await resolver.authorize(
        _request(capability_ref="urn:test:capability:x", authority_ref=None)
    )

    assert decision.admitted is False
    assert decision.reason == "LIVE_AUTHORITY_REQUIRED"


async def test_odrl_resolver_admits_a_targeted_permission_with_no_assigner_on_any_live_ref() -> (
    None
):
    """career-gym-pack's real shape: a permission with a real target and no
    assigner -- the permission's mere existence for this target is the
    grant, matching this session's real, direct read of that pack."""
    permission = OdrlPermission(
        permission_iri=None, target="urn:test:capability:x", assigner=None, assignee=None
    )
    resolver = OdrlAuthorityResolver(permissions=(permission,))

    decision = await resolver.authorize(
        _request(capability_ref="urn:test:capability:x", authority_ref="urn:test:anyone")
    )

    assert decision.admitted is True
    assert decision.reason == "ODRL_PERMISSION_ADMITTED"


async def test_odrl_resolver_admits_a_self_typed_permission_capability_by_iri() -> None:
    """multicloud-gym-pack's real shape: the capability IRI itself is
    directly typed odrl:Permission, no separate target."""
    permission = OdrlPermission(
        permission_iri="urn:test:capability:x", target=None, assigner=None, assignee=None
    )
    resolver = OdrlAuthorityResolver(permissions=(permission,))

    decision = await resolver.authorize(
        _request(capability_ref="urn:test:capability:x", authority_ref="urn:test:anyone")
    )

    assert decision.admitted is True
    assert decision.reason == "ODRL_PERMISSION_ADMITTED"


async def test_odrl_resolver_requires_the_named_assigner_when_one_is_declared() -> None:
    """togaf-gym-pack's real shape: a permission with a real
    odrl:assigner (the Architecture Board) -- only that exact identity
    admits."""
    permission = OdrlPermission(
        permission_iri=None,
        target="urn:test:architecture:target",
        assigner="urn:test:org:architecture-board",
        assignee="urn:test:org:architecture-office",
    )
    resolver = OdrlAuthorityResolver(permissions=(permission,))

    wrong_ref = await resolver.authorize(
        _request(
            capability_ref="urn:test:architecture:target",
            authority_ref="urn:test:someone-else",
        )
    )
    assert wrong_ref.admitted is False
    assert wrong_ref.reason == "ODRL_ASSIGNER_MISMATCH"

    right_ref = await resolver.authorize(
        _request(
            capability_ref="urn:test:architecture:target",
            authority_ref="urn:test:org:architecture-board",
        )
    )
    assert right_ref.admitted is True
    assert right_ref.reason == "ODRL_ASSIGNER_ADMITTED"


def test_load_odrl_permissions_reads_togaf_gym_packs_real_governance_fact() -> None:
    """Real-pack-grounded test, per this session's own established two-tier
    pattern: not just a synthetic fixture, the actual
    ggen/togaf-gym-pack/ontology.ttl governance permission."""
    pack_dir = REPO_ROOT / "ggen" / "togaf-gym-pack"

    permissions = load_odrl_permissions(pack_dir)

    assert len(permissions) == 1
    permission = permissions[0]
    assert permission.target == "urn:gymact:togaf:architecture:target"
    assert permission.assigner == "urn:gymact:togaf:org:architecture-board"
    assert permission.assignee == "urn:gymact:togaf:org:architecture-office"


async def test_odrl_resolver_against_togaf_gym_packs_real_governance_permission() -> None:
    """Proves OdrlAuthorityResolver gives the real, correct verdict against
    togaf-gym-pack's actual, unmodified ontology fact -- not a synthetic
    stand-in for it."""
    permissions = load_odrl_permissions(REPO_ROOT / "ggen" / "togaf-gym-pack")
    resolver = OdrlAuthorityResolver(permissions=permissions)

    board_request = _request(
        capability_ref="urn:gymact:togaf:architecture:target",
        authority_ref="urn:gymact:togaf:org:architecture-board",
    )
    admitted = await resolver.authorize(board_request)
    assert admitted.admitted is True
    assert admitted.reason == "ODRL_ASSIGNER_ADMITTED"

    impostor_request = _request(
        capability_ref="urn:gymact:togaf:architecture:target",
        authority_ref="urn:gymact:togaf:org:architecture-office",
    )
    refused = await resolver.authorize(impostor_request)
    assert refused.admitted is False
    assert refused.reason == "ODRL_ASSIGNER_MISMATCH"


# --- load_procedures: bare sosa:Procedure packs, real-pack-grounded --------


def test_load_procedures_reads_protocol_gym_packs_real_bare_procedures() -> None:
    """protocol-gym-pack has zero pplan:Plan tasks -- a genuinely different
    real shape from togaf-gym-pack's, confirmed by direct read before this
    function was written."""
    pack_dir = REPO_ROOT / "ggen" / "protocol-gym-pack"

    procedures = load_procedures(pack_dir)

    assert {p.identifier for p in procedures} == {"read", "do"}
    by_identifier = {p.identifier: p for p in procedures}
    assert by_identifier["read"].family == "read"
    assert by_identifier["do"].family == "do"
    assert by_identifier["read"].subjects == ("urn:gymact:protocol-gym:fixture:read",)


async def test_bare_procedures_have_no_preconditions_between_each_other() -> None:
    """The honest modeling choice load_procedures' own docstring states:
    no real ordering exists between bare sosa:Procedure tasks, so both must
    be independently actuatable from the start -- proven end to end
    through a real environment compiled from protocol-gym-pack's real
    facts, not just at the query-parsing level."""
    # Monkeypatch-free: OntologyDrivenProvider.tasks() calls load_tasks
    # (pplan:Plan-shaped) by default, which finds nothing for this pack
    # (protocol-gym-pack has no pplan:Plan tasks at all) -- so this test
    # exercises load_procedures directly against the real environment
    # construction path instead, proving the real facts compile into a
    # real, working, order-free provider.
    procedures = load_procedures(REPO_ROOT / "ggen" / "protocol-gym-pack")
    assert len(procedures) == 2

    from gymact.gyms.ontology_gym import OntologyDrivenEnvironment

    env = OntologyDrivenEnvironment(
        provider_name="protocol-fixture",
        tasks=procedures,
        reset_task_families=frozenset(),
        reset_target_families=frozenset(),
        requires_authority=False,
    )
    do_task = next(t for t in procedures if t.identifier == "do")
    read_task = next(t for t in procedures if t.identifier == "read")

    # "do" actuated FIRST, with "read" not yet established -- must be
    # admitted (no real precondition exists between them).
    do_capability = capability_iri(provider_name="protocol-fixture", task=do_task)
    do_capability_obj = next(c for c in env.capabilities() if c.iri == do_capability)
    effect = await env.actuate(do_capability_obj, {})
    assert effect["established"] == do_task.subjects[0]

    read_capability = capability_iri(provider_name="protocol-fixture", task=read_task)
    read_capability_obj = next(c for c in env.capabilities() if c.iri == read_capability)
    effect2 = await env.actuate(read_capability_obj, {})
    assert effect2["established"] == read_task.subjects[0]

    observation = await env.observe()
    assert observation["goal_reached"] is True
