"""Ontology-parity and real functional tests for the SIMULATED multicloud gym.

Chicago-style throughout: every test drives the real `gymact.gyms.multicloud`
provider through the real `gymact.runtime.GymAct` orchestrator (or, for the
parity test, the real `ggen/multicloud-gym-pack/ontology.ttl` file parsed
with real `rdflib`) -- no interaction-verifying test doubles of any kind
anywhere in this file (this repo's testing-discipline grep over this file
must report zero hits). State-based assertions on real returned/observed
values throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.namespace import DCTERMS

from gymact.authority import AllowListAuthorityResolver
from gymact.gyms.multicloud import CAPABILITY_REGISTRY, MulticloudProvider
from gymact.models import ActuationIntent, Consequence, MaterializationIntent, Standing
from gymact.runtime import GymAct

SOSA = Namespace("http://www.w3.org/ns/sosa/")
_CONSEQUENCE_BY_IRI = {
    "urn:gymact:consequence:read": Consequence.READ,
    "urn:gymact:consequence:do": Consequence.DO,
}

_ONTOLOGY_PATH = (
    Path(__file__).resolve().parents[1] / "ggen" / "multicloud-gym-pack" / "ontology.ttl"
)

AUTHORITY = "urn:test:multicloud-authority"


def _ontology_procedures() -> dict[str, tuple[str, Consequence]]:
    """Real parse of the real ontology file: iri -> (title, consequence)."""
    graph = Graph()
    graph.parse(_ONTOLOGY_PATH, format="turtle")
    procedures: dict[str, tuple[str, Consequence]] = {}
    for subject in graph.subjects(RDF.type, SOSA.Procedure):
        titles = list(graph.objects(subject, DCTERMS.title))
        types = list(graph.objects(subject, DCTERMS.type))
        assert len(titles) == 1, f"{subject} must have exactly one dct:title, got {titles}"
        assert len(types) == 1, f"{subject} must have exactly one dct:type, got {types}"
        consequence = _CONSEQUENCE_BY_IRI[str(types[0])]
        procedures[str(subject)] = (str(titles[0]), consequence)
    return procedures


def test_ontology_file_exists_and_is_nonempty() -> None:
    assert _ONTOLOGY_PATH.is_file(), f"ontology file missing: {_ONTOLOGY_PATH}"
    assert _ONTOLOGY_PATH.stat().st_size > 0


def test_capability_registry_matches_ontology_exactly() -> None:
    """Code and ontology cannot silently diverge, in either direction."""
    ontology = _ontology_procedures()
    registry = {
        capability.iri: (capability.title, capability.consequence)
        for capability in CAPABILITY_REGISTRY
    }

    missing_from_registry = set(ontology) - set(registry)
    extra_in_registry = set(registry) - set(ontology)
    assert not missing_from_registry, (
        f"ontology.ttl declares sosa:Procedure nodes absent from CAPABILITY_REGISTRY: "
        f"{sorted(missing_from_registry)}"
    )
    assert not extra_in_registry, (
        f"CAPABILITY_REGISTRY has capabilities absent from ontology.ttl: "
        f"{sorted(extra_in_registry)}"
    )

    drifted = {
        iri: {"ontology": ontology[iri], "registry": registry[iri]}
        for iri in ontology
        if ontology[iri] != registry[iri]
    }
    assert not drifted, f"title/consequence drift between ontology and registry: {drifted}"


def test_capability_registry_has_unique_iris_and_bindings() -> None:
    iris = [capability.iri for capability in CAPABILITY_REGISTRY]
    bindings = [capability.binding for capability in CAPABILITY_REGISTRY]
    assert len(iris) == len(set(iris)), "duplicate capability IRIs in CAPABILITY_REGISTRY"
    assert len(bindings) == len(set(bindings)), "duplicate capability bindings in CAPABILITY_REGISTRY"


def test_capability_registry_covers_all_three_clouds() -> None:
    by_cloud: dict[str, int] = {"aws": 0, "azure": 0, "gcp": 0}
    for capability in CAPABILITY_REGISTRY:
        for cloud in by_cloud:
            if f":multicloud:{cloud}:capability:" in capability.iri:
                by_cloud[cloud] += 1
                break
    assert all(count > 0 for count in by_cloud.values()), by_cloud


# ---------------------------------------------------------------------------
# Real functional tests through the real GymAct orchestrator.
# ---------------------------------------------------------------------------


def _capability(binding: str) -> str:
    for capability in CAPABILITY_REGISTRY:
        if capability.binding == binding:
            return capability.iri
    raise AssertionError(f"no capability with binding {binding}")


AWS_CREATE_ROLE = _capability("aws_iam_create_role")
AWS_ATTACH_POLICY = _capability("aws_iam_attach_role_policy")
AWS_CREATE_BUCKET = _capability("aws_s3_create_bucket")
AWS_RUN_INSTANCES = _capability("aws_ec2_run_instances")
AZURE_CREATE_STORAGE_ACCOUNT = _capability("azure_storage_create_account")
AZURE_CREATE_VM = _capability("azure_compute_create_virtual_machine")
GCP_CREATE_SERVICE_ACCOUNT = _capability("gcp_iam_create_service_account")
GCP_ADD_POLICY_BINDING = _capability("gcp_iam_add_iam_policy_binding")
GCP_CREATE_INSTANCE = _capability("gcp_compute_create_instance")


def authorized_runtime() -> GymAct:
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    runtime.register_provider(MulticloudProvider())
    return runtime


async def materialize(runtime: GymAct, *, key: str):
    result = await runtime.materialize(
        MaterializationIntent(provider="multicloud", idempotency_key=key)
    )
    assert result.accepted is True
    assert result.episode is not None
    assert result.observation is not None
    return result


@pytest.mark.asyncio
async def test_environment_requires_authority_by_default() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="default-authority")
    episode = materialized.episode
    assert episode is not None
    capabilities = runtime.capabilities(episode.episode_id)
    assert {c.binding for c in capabilities} == {c.binding for c in CAPABILITY_REGISTRY}


@pytest.mark.asyncio
async def test_do_actuation_without_authority_is_refused_and_world_unchanged() -> None:
    runtime = GymAct()
    runtime.register_provider(MulticloudProvider())
    materialized = await materialize(runtime, key="refused-materialize")
    episode = materialized.episode
    assert episode is not None

    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=AWS_CREATE_ROLE,
            payload={"role_name": "gymact-refused-role"},
            idempotency_key="refused-role-create",
        )
    )
    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "LIVE_AUTHORITY_REQUIRED"

    observation = await runtime.observe(episode.episode_id)
    assert observation.state["aws"]["iam_roles"] == {}
    assert result.receipt.pre_state_digest == result.receipt.post_state_digest


@pytest.mark.asyncio
async def test_admitted_authority_actuates_aws_iam_create_role_and_attach_policy() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="aws-iam-materialize")
    episode = materialized.episode
    assert episode is not None

    create_result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=AWS_CREATE_ROLE,
            payload={"role_name": "gymact-app-role"},
            authority_ref=AUTHORITY,
            idempotency_key="aws-create-role",
        )
    )
    assert create_result.accepted is True
    assert create_result.standing == Standing.ALIVE
    assert create_result.receipt.authority_evidence_ref is not None

    observation = await runtime.observe(episode.episode_id)
    role = observation.state["aws"]["iam_roles"]["gymact-app-role"]
    assert role["role_name"] == "gymact-app-role"
    assert role["arn"] == "arn:aws:iam::123456789012:role/gymact-app-role"

    attach_result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=AWS_ATTACH_POLICY,
            payload={
                "role_name": "gymact-app-role",
                "policy_arn": "arn:aws:iam::aws:policy/ReadOnlyAccess",
            },
            authority_ref=AUTHORITY,
            idempotency_key="aws-attach-policy",
        )
    )
    assert attach_result.accepted is True
    observation = await runtime.observe(episode.episode_id)
    attachments = observation.state["aws"]["iam_role_policy_attachments"]["gymact-app-role"]
    assert attachments == ["arn:aws:iam::aws:policy/ReadOnlyAccess"]

    verification = await runtime.verify(
        episode.episode_id,
        {"aws": observation.state["aws"]},
    )
    assert verification.passed is True


@pytest.mark.asyncio
async def test_attach_policy_to_nonexistent_role_is_blocked_not_silent() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="aws-attach-missing-role")
    episode = materialized.episode
    assert episode is not None

    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=AWS_ATTACH_POLICY,
            payload={"role_name": "does-not-exist", "policy_arn": "arn:aws:iam::aws:policy/X"},
            authority_ref=AUTHORITY,
            idempotency_key="attach-missing-role",
        )
    )
    assert result.accepted is False
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason.startswith("PROVIDER_ERROR:")


@pytest.mark.asyncio
async def test_read_capability_cannot_be_actuated() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="read-cannot-actuate")
    episode = materialized.episode
    assert episode is not None

    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=_capability("aws_iam_list_roles"),
            payload={},
            authority_ref=AUTHORITY,
            idempotency_key="read-as-actuation",
        )
    )
    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "READ_CAPABILITY_IS_NOT_ACTUATION"


@pytest.mark.asyncio
async def test_actuation_is_idempotent() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="idempotent-materialize")
    episode = materialized.episode
    assert episode is not None

    intent = ActuationIntent(
        episode_id=episode.episode_id,
        capability=AWS_CREATE_BUCKET,
        payload={"bucket_name": "gymact-simulated-bucket"},
        authority_ref=AUTHORITY,
        idempotency_key="create-bucket-once",
    )
    first = await runtime.act(intent)
    second = await runtime.act(intent)
    assert first == second

    observation = await runtime.observe(episode.episode_id)
    assert list(observation.state["aws"]["storage_buckets"]) == ["gymact-simulated-bucket"]


@pytest.mark.asyncio
async def test_checkpoint_and_restore_round_trip_real_state() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="checkpoint-materialize")
    episode = materialized.episode
    assert episode is not None

    await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=AWS_RUN_INSTANCES,
            payload={"instance_type": "t3.micro"},
            authority_ref=AUTHORITY,
            idempotency_key="run-before-checkpoint",
        )
    )
    checkpoint = await runtime.checkpoint(episode.episode_id)
    assert checkpoint["aws"]["compute_instances"], "checkpoint must reflect the real instance"

    second_actuation = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=AWS_RUN_INSTANCES,
            payload={"instance_type": "t3.micro"},
            authority_ref=AUTHORITY,
            idempotency_key="run-after-checkpoint",
        )
    )
    assert second_actuation.accepted is True
    observation = await runtime.observe(episode.episode_id)
    assert len(observation.state["aws"]["compute_instances"]) == 2

    restore_receipt = await runtime.restore(
        episode.episode_id, checkpoint, authority_ref=AUTHORITY
    )
    assert restore_receipt.standing == Standing.ALIVE

    restored = await runtime.observe(episode.episode_id)
    assert len(restored.state["aws"]["compute_instances"]) == 1


@pytest.mark.asyncio
async def test_restore_without_authority_is_refused_and_state_unchanged() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="restore-refused-materialize")
    episode = materialized.episode
    assert episode is not None

    await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=AWS_CREATE_BUCKET,
            payload={"bucket_name": "gymact-restore-guard"},
            authority_ref=AUTHORITY,
            idempotency_key="restore-guard-create",
        )
    )
    checkpoint = await runtime.checkpoint(episode.episode_id)

    receipt = await runtime.restore(episode.episode_id, {"aws": {}, "azure": {}, "gcp": {}})
    assert receipt.standing == Standing.REFUSED
    assert receipt.reason == "LIVE_AUTHORITY_REQUIRED"

    observation = await runtime.observe(episode.episode_id)
    assert observation.state == checkpoint


@pytest.mark.asyncio
async def test_teardown_is_idempotent_and_final() -> None:
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="teardown-materialize")
    episode = materialized.episode
    assert episode is not None

    first = await runtime.teardown(episode.episode_id, authority_ref=AUTHORITY)
    second = await runtime.teardown(episode.episode_id, authority_ref=AUTHORITY)
    assert first == second
    assert first.standing == Standing.ALIVE


@pytest.mark.asyncio
async def test_cross_cloud_scenario_coexisting_real_state_mutations() -> None:
    """One episode: an AWS IAM role, an Azure storage account, and a GCP
    compute instance are all created and independently verified to coexist."""
    runtime = authorized_runtime()
    materialized = await materialize(runtime, key="cross-cloud-materialize")
    episode = materialized.episode
    assert episode is not None
    episode_id = episode.episode_id

    aws_result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=AWS_CREATE_ROLE,
            payload={"role_name": "gymact-cross-cloud-role"},
            authority_ref=AUTHORITY,
            idempotency_key="cross-cloud-aws-role",
        )
    )
    assert aws_result.accepted is True

    azure_result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=AZURE_CREATE_STORAGE_ACCOUNT,
            payload={"account_name": "gymactcrosscloud"},
            authority_ref=AUTHORITY,
            idempotency_key="cross-cloud-azure-storage",
        )
    )
    assert azure_result.accepted is True

    azure_vm_result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=AZURE_CREATE_VM,
            payload={"vm_name": "gymact-cross-cloud-vm"},
            authority_ref=AUTHORITY,
            idempotency_key="cross-cloud-azure-vm",
        )
    )
    assert azure_vm_result.accepted is True

    gcp_sa_result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GCP_CREATE_SERVICE_ACCOUNT,
            payload={"account_id": "gymact-cross-cloud-sa"},
            authority_ref=AUTHORITY,
            idempotency_key="cross-cloud-gcp-sa",
        )
    )
    assert gcp_sa_result.accepted is True

    gcp_binding_result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GCP_ADD_POLICY_BINDING,
            payload={
                "member": "serviceAccount:gymact-cross-cloud-sa@gymact-simulated-project.iam.gserviceaccount.com",
                "role": "roles/viewer",
            },
            authority_ref=AUTHORITY,
            idempotency_key="cross-cloud-gcp-binding",
        )
    )
    assert gcp_binding_result.accepted is True

    gcp_instance_result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GCP_CREATE_INSTANCE,
            payload={"instance_name": "gymact-cross-cloud-instance"},
            authority_ref=AUTHORITY,
            idempotency_key="cross-cloud-gcp-instance",
        )
    )
    assert gcp_instance_result.accepted is True

    observation = await runtime.observe(episode_id)
    state = observation.state

    assert state["aws"]["iam_roles"]["gymact-cross-cloud-role"]["arn"] == (
        "arn:aws:iam::123456789012:role/gymact-cross-cloud-role"
    )
    assert state["azure"]["storage_accounts"]["gymactcrosscloud"]["account_name"] == (
        "gymactcrosscloud"
    )
    assert state["azure"]["compute_instances"]["gymact-cross-cloud-vm"]["vm_name"] == (
        "gymact-cross-cloud-vm"
    )
    assert state["gcp"]["iam_service_accounts"]["gymact-cross-cloud-sa"]["account_id"] == (
        "gymact-cross-cloud-sa"
    )
    assert state["gcp"]["iam_policy_bindings"]["roles/viewer"] == [
        "serviceAccount:gymact-cross-cloud-sa@gymact-simulated-project.iam.gserviceaccount.com"
    ]
    assert (
        state["gcp"]["compute_instances"]["gymact-cross-cloud-instance"]["name"]
        == "projects/gymact-simulated-project/zones/us-central1-a/instances/gymact-cross-cloud-instance"
    )

    verification = await runtime.verify(
        episode_id,
        {
            "aws": state["aws"],
            "azure": state["azure"],
            "gcp": state["gcp"],
        },
    )
    assert verification.passed is True

    teardown_receipt = await runtime.teardown(episode_id, authority_ref=AUTHORITY)
    assert teardown_receipt.standing == Standing.ALIVE
