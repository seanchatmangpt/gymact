from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from rdflib import RDF, Graph, Namespace
from rdflib.namespace import DCTERMS

from gymact.authority import AllowListAuthorityResolver
from gymact.gyms.cloudsim import (
    CLOUDSIM_CAPABILITIES,
    DEFAULT_GLOBAL_TOPOLOGY,
    SERVICE_FAMILIES,
    CloudSimProvider,
    service_catalog_size,
)
from gymact.models import ActuationIntent, Consequence, MaterializationIntent, Standing
from gymact.providers import EnvironmentProvider
from gymact.registry import (
    builtin_capabilities,
    builtin_provider_names,
    create_builtin_provider,
    describe_builtin_provider,
)
from gymact.runtime import GymAct

SOSA = Namespace("http://www.w3.org/ns/sosa/")
AUTHORITY = "urn:test:cloudsim-authority"
ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ggen" / "cloudsim-gym-pack" / "ontology.ttl"
SOURCE = ROOT / "src" / "gymact" / "gyms" / "cloudsim"


def capability(binding: str) -> str:
    for item in CLOUDSIM_CAPABILITIES:
        if item.binding == binding:
            return item.iri
    raise AssertionError(f"missing capability: {binding}")


def runtime(*, config_authority: bool = True) -> GymAct:
    resolver = AllowListAuthorityResolver({AUTHORITY}) if config_authority else None
    value = GymAct(authority_resolver=resolver)
    value.register_provider(CloudSimProvider())
    return value


async def materialize(value: GymAct, *, key: str, config: dict[str, Any] | None = None):
    result = await value.materialize(
        MaterializationIntent(
            provider="cloudsim",
            config=config or {},
            idempotency_key=key,
        )
    )
    assert result.accepted is True
    assert result.episode is not None
    return result.episode


async def apply(
    value: GymAct,
    *,
    episode_id: str,
    cloud: str,
    payload: dict[str, Any],
    key: str,
    authority_ref: str | None = AUTHORITY,
):
    return await value.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability(f"{cloud}_cloudsim_apply"),
            payload=payload,
            authority_ref=authority_ref,
            idempotency_key=key,
        )
    )


def create_payload(
    *,
    service: str,
    operation: str,
    resource_type: str,
    name: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "service": service,
        "operation": operation,
        "effect": "CREATE",
        "resource_type": resource_type,
        "name": name,
        **extra,
    }


def result_resource_id(result: Any) -> str:
    assert result.effect is not None
    return str(result.effect["result"]["resource"]["id"])


def test_provider_satisfies_gymact_environment_provider_contract() -> None:
    assert isinstance(CloudSimProvider(), EnvironmentProvider)


def test_cloudsim_is_first_class_builtin_provider() -> None:
    assert "cloudsim" in builtin_provider_names()
    provider = create_builtin_provider("cloudsim")
    assert isinstance(provider, CloudSimProvider)
    assert builtin_capabilities("cloudsim") == CLOUDSIM_CAPABILITIES
    description = describe_builtin_provider("cloudsim")
    assert description["type"] == "CloudSimProvider"
    assert len(description["capabilities"]) == 4


def test_capabilities_are_unique_consequential_do_operations() -> None:
    iris = [item.iri for item in CLOUDSIM_CAPABILITIES]
    bindings = [item.binding for item in CLOUDSIM_CAPABILITIES]
    assert len(iris) == len(set(iris)) == 4
    assert len(bindings) == len(set(bindings)) == 4
    assert all(item.consequence is Consequence.DO for item in CLOUDSIM_CAPABILITIES)


def test_ontology_and_python_capabilities_match_exactly() -> None:
    graph = Graph()
    graph.parse(ONTOLOGY, format="turtle")
    observed: dict[str, tuple[str, str]] = {}
    for subject in graph.subjects(RDF.type, SOSA.Procedure):
        titles = list(graph.objects(subject, DCTERMS.title))
        types = list(graph.objects(subject, DCTERMS.type))
        assert len(titles) == 1
        assert len(types) == 1
        observed[str(subject)] = (str(titles[0]), str(types[0]))
    expected = {
        item.iri: (item.title, "urn:gymact:consequence:do") for item in CLOUDSIM_CAPABILITIES
    }
    assert observed == expected


def test_cloudsim_source_has_zero_vendor_cloud_sdk_imports() -> None:
    imported: set[str] = set()
    for source_path in SOURCE.glob("*.py"):
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    forbidden = ("boto3", "botocore", "azure", "google.cloud")
    assert not sorted(name for name in imported if name.startswith(forbidden))


def test_seed_catalog_is_broad_but_topology_is_data() -> None:
    assert set(SERVICE_FAMILIES) == {"aws", "azure", "gcp"}
    assert service_catalog_size() == 62
    for topology in DEFAULT_GLOBAL_TOPOLOGY.values():
        assert len(topology["scopes"]) == 3
        assert len(topology["regions"]) == 6


@pytest.mark.asyncio
async def test_missing_authority_refuses_do_and_leaves_world_unchanged() -> None:
    value = runtime(config_authority=False)
    episode = await materialize(value, key="no-authority-materialize")
    before = await value.observe(episode.episode_id)
    result = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="aws",
        payload=create_payload(
            service="rds",
            operation="CreateDBInstance",
            resource_type="database",
            name="orders",
        ),
        key="no-authority-act",
        authority_ref=None,
    )
    assert result.accepted is False
    assert result.standing is Standing.REFUSED
    assert result.receipt.reason == "LIVE_AUTHORITY_REQUIRED"
    assert result.receipt.pre_state_digest == result.receipt.post_state_digest
    after = await value.observe(episode.episode_id)
    assert after.state == before.state


@pytest.mark.asyncio
async def test_same_finite_kernel_runs_multi_service_multi_cloud_world() -> None:
    value = runtime()
    episode = await materialize(value, key="global-materialize")
    cases = (
        (
            "aws",
            create_payload(
                service="rds",
                operation="CreateDBInstance",
                resource_type="database",
                name="orders",
            ),
        ),
        (
            "aws",
            create_payload(
                service="s3",
                operation="CreateBucket",
                resource_type="bucket",
                name="archive",
            ),
        ),
        (
            "azure",
            create_payload(
                service="keyvault",
                operation="Vaults_CreateOrUpdate",
                resource_type="vault",
                name="secrets",
            ),
        ),
        (
            "azure",
            create_payload(
                service="aks",
                operation="ManagedClusters_CreateOrUpdate",
                resource_type="cluster",
                name="prod-aks",
            ),
        ),
        (
            "gcp",
            create_payload(
                service="pubsub",
                operation="projects.topics.create",
                resource_type="topic",
                name="orders",
            ),
        ),
        (
            "gcp",
            create_payload(
                service="bigquery",
                operation="datasets.insert",
                resource_type="dataset",
                name="analytics",
            ),
        ),
    )
    receipts = []
    for index, (cloud, payload) in enumerate(cases):
        result = await apply(
            value,
            episode_id=episode.episode_id,
            cloud=cloud,
            payload=payload,
            key=f"global-{index}",
        )
        assert result.accepted is True
        assert result.standing is Standing.ALIVE
        assert result.receipt.authority_evidence_ref is not None
        receipts.append(result.receipt.receipt_id)
    observed = await value.observe(episode.episode_id)
    assert sum(len(resources) for resources in observed.state["resources"].values()) == 6
    assert len(set(receipts)) == 6


@pytest.mark.asyncio
async def test_novel_service_and_operation_need_no_new_source_branch() -> None:
    value = runtime()
    episode = await materialize(value, key="novel-service-materialize")
    result = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="gcp",
        payload=create_payload(
            service="quantum-control-plane-2099",
            operation="projects.fabric.create",
            resource_type="fabric",
            name="future",
        ),
        key="novel-service-create",
    )
    assert result.accepted is True
    observed = await value.observe(episode.episode_id)
    resource = next(iter(observed.state["resources"]["gcp"].values()))
    assert resource["service"] == "quantum-control-plane-2099"


@pytest.mark.asyncio
async def test_eventual_consistency_is_deterministic_and_receipted() -> None:
    value = runtime()
    episode = await materialize(value, key="visibility-materialize")
    created = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="aws",
        payload=create_payload(
            service="dynamodb",
            operation="CreateTable",
            resource_type="table",
            name="ledger",
            visibility_delay=2,
        ),
        key="visibility-create",
    )
    resource_id = result_resource_id(created)
    observed = await value.observe(episode.episode_id)
    assert observed.state["resources"]["aws"][resource_id]["visible"] is False

    advanced = await value.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=capability("cloudsim_advance_clock"),
            payload={"ticks": 2},
            authority_ref=AUTHORITY,
            idempotency_key="advance-clock",
        )
    )
    assert advanced.accepted is True
    assert advanced.receipt.authority_evidence_ref is not None
    observed = await value.observe(episode.episode_id)
    assert observed.state["resources"]["aws"][resource_id]["visible"] is True


@pytest.mark.asyncio
async def test_injected_provider_fault_blocks_once_without_resource_mutation() -> None:
    value = runtime()
    episode = await materialize(
        value,
        key="fault-materialize",
        config={"faults": {"aws:rds:CreateDBInstance": 1}},
    )
    payload = create_payload(
        service="rds",
        operation="CreateDBInstance",
        resource_type="database",
        name="orders",
    )
    failed = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="aws",
        payload=payload,
        key="fault-first",
    )
    assert failed.accepted is False
    assert failed.standing is Standing.BLOCKED
    assert failed.receipt.reason == "PROVIDER_ERROR:RuntimeError"
    assert failed.receipt.pre_state_digest == failed.receipt.post_state_digest

    retried = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="aws",
        payload=payload,
        key="fault-second",
    )
    assert retried.accepted is True


@pytest.mark.asyncio
async def test_quota_exhaustion_blocks_without_partial_resource_creation() -> None:
    value = runtime()
    episode = await materialize(
        value,
        key="quota-materialize",
        config={"quotas": {"gcp:gke:cluster": 1}},
    )
    first = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="gcp",
        payload=create_payload(
            service="gke",
            operation="projects.locations.clusters.create",
            resource_type="cluster",
            name="primary",
        ),
        key="quota-first",
    )
    assert first.accepted is True
    second = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="gcp",
        payload=create_payload(
            service="gke",
            operation="projects.locations.clusters.create",
            resource_type="cluster",
            name="secondary",
        ),
        key="quota-second",
    )
    assert second.accepted is False
    assert second.receipt.pre_state_digest == second.receipt.post_state_digest
    observed = await value.observe(episode.episode_id)
    assert len(observed.state["resources"]["gcp"]) == 1


@pytest.mark.asyncio
async def test_dependency_law_refuses_parent_delete_while_child_is_active() -> None:
    value = runtime()
    episode = await materialize(value, key="dependency-materialize")
    network = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="azure",
        payload=create_payload(
            service="network",
            operation="VirtualNetworks_CreateOrUpdate",
            resource_type="virtualNetwork",
            name="core",
        ),
        key="network-create",
    )
    network_id = result_resource_id(network)
    child = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="azure",
        payload=create_payload(
            service="compute",
            operation="VirtualMachines_CreateOrUpdate",
            resource_type="virtualMachine",
            name="api",
            depends_on=[network_id],
        ),
        key="vm-create",
    )
    assert child.accepted is True
    refused = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="azure",
        payload={
            "service": "network",
            "operation": "VirtualNetworks_Delete",
            "effect": "DELETE",
            "resource_id": network_id,
        },
        key="network-delete",
    )
    assert refused.accepted is False
    assert refused.standing is Standing.BLOCKED
    assert refused.receipt.pre_state_digest == refused.receipt.post_state_digest


@pytest.mark.asyncio
async def test_custom_topology_scales_without_provider_code_changes() -> None:
    scopes = [f"business-unit-{index}" for index in range(20)]
    regions = [f"global-region-{index}" for index in range(12)]
    topology = {
        cloud: {"scopes": scopes, "regions": regions} for cloud in ("aws", "azure", "gcp")
    }
    value = runtime()
    episode = await materialize(
        value,
        key="topology-materialize",
        config={"topology": topology},
    )
    result = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="aws",
        payload=create_payload(
            service="eks",
            operation="CreateCluster",
            resource_type="cluster",
            name="global",
            scope="business-unit-19",
            region="global-region-11",
        ),
        key="topology-create",
    )
    assert result.accepted is True


@pytest.mark.asyncio
async def test_checkpoint_restore_replays_world_and_simulation_controls() -> None:
    value = runtime()
    episode = await materialize(value, key="checkpoint-materialize")
    first = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="aws",
        payload=create_payload(
            service="s3",
            operation="CreateBucket",
            resource_type="bucket",
            name="first",
        ),
        key="checkpoint-first",
    )
    assert first.accepted is True
    checkpoint = await value.checkpoint(episode.episode_id)
    second = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="aws",
        payload=create_payload(
            service="s3",
            operation="CreateBucket",
            resource_type="bucket",
            name="second",
        ),
        key="checkpoint-second",
    )
    assert second.accepted is True
    before_restore = await value.observe(episode.episode_id)
    assert len(before_restore.state["resources"]["aws"]) == 2

    receipt = await value.restore(episode.episode_id, checkpoint, authority_ref=AUTHORITY)
    assert receipt.standing is Standing.ALIVE
    after_restore = await value.observe(episode.episode_id)
    assert len(after_restore.state["resources"]["aws"]) == 1


@pytest.mark.asyncio
async def test_verification_observes_real_simulated_postcondition() -> None:
    value = runtime()
    episode = await materialize(value, key="verify-materialize")
    result = await apply(
        value,
        episode_id=episode.episode_id,
        cloud="gcp",
        payload=create_payload(
            service="bigquery",
            operation="datasets.insert",
            resource_type="dataset",
            name="finance",
        ),
        key="verify-create",
    )
    assert result.accepted is True
    observed = await value.observe(episode.episode_id)
    verification = await value.verify(
        episode.episode_id,
        {"resources": observed.state["resources"]},
    )
    assert verification.passed is True
    assert verification.state_digest == observed.state_digest
