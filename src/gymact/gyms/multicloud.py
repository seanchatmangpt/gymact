"""SIMULATED GymAct `Environment`/`EnvironmentProvider` for a multicloud
(AWS/Azure/GCP) IAM/storage/compute gym.

THIS PROVIDER IS SIMULATED. Every operation it exposes is a real, in-memory
Python state-machine mutation over plain `dict`s -- there is zero network
I/O, zero cloud SDK dependency (`boto3`, `azure-sdk-for-python`, and the GCP
client libraries are NOT imported anywhere in this module), zero
credentials of any kind, and zero calls to any real AWS/Azure/GCP API. The
operation names (`aws.iam.create_role`, `azure.compute.create_virtual_machine`,
`gcp.storage.create_bucket`, ...) and the generated resource identifiers
(ARN-shaped for AWS, resource-ID-shaped for Azure, resource-name-shaped for
GCP) are chosen to *look like* what each real cloud's own SDK would return,
purely so a reader already familiar with any of the three real SDKs
recognizes the shape immediately -- not because this module talks to any
real cloud. `_AWS_ACCOUNT_ID`, `_AZURE_SUBSCRIPTION_ID`, `_AZURE_RESOURCE_GROUP`,
and `_GCP_PROJECT_ID` below are fixed, obviously-fake placeholder values
documented as such; no real account/subscription/project is ever contacted
or referenced.

`CAPABILITY_REGISTRY` is the Python projection of every `sosa:Procedure`
declared in `ggen/multicloud-gym-pack/ontology.ttl`: one `Capability` per
ontology node, with `iri`/`title`/`consequence` copied verbatim from that
file's `dct:title`/`dct:type` facts. `tests/test_multicloud.py`'s
ontology-parity test parses the real ontology file with `rdflib` and fails
loudly if this tuple and that file ever diverge in either direction --
mirroring `ggen/gymact-bridge-pack`'s `operation_catalog_proof.rs.tmpl`
pattern, in Python/pytest instead of Rust.

Per `.claude/rules/actuation-authority.md`, `MulticloudEnvironment` defaults
`requires_authority=True`: every DO capability here models a genuinely
consequential real-world cloud action (create an IAM role, attach a policy,
provision a VM, ...) even though this particular execution is simulated,
so the runtime's normal authority boundary (`gymact.kernel.GymAct.act`)
must be crossed before any of them mutate state. READ capabilities are
never authority-gated by the runtime (see `GymAct.act`'s
`capability.consequence is not Consequence.DO` short-circuit, which refuses
*any* attempt to actuate a READ capability, DO-authority-gating decided
entirely by the runtime, not re-implemented here) -- this provider does not
duplicate that check.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

# Fixed, obviously-simulated placeholder identifiers. None of these resolve
# to a real AWS account, Azure subscription, or GCP project.
_AWS_ACCOUNT_ID = "123456789012"
_AWS_REGION = "us-east-1"
_AZURE_SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000000"
_AZURE_RESOURCE_GROUP = "gymact-simulated-rg"
_GCP_PROJECT_ID = "gymact-simulated-project"
_GCP_DEFAULT_ZONE = "us-central1-a"

CAPABILITY_REGISTRY: tuple[Capability, ...] = (
    # -- AWS (boto3-style operation names) -----------------------------
    Capability(
        iri="urn:gymact:multicloud:aws:capability:iam.create_role",
        title="aws.iam.create_role",
        consequence=Consequence.DO,
        binding="aws_iam_create_role",
    ),
    Capability(
        iri="urn:gymact:multicloud:aws:capability:iam.attach_role_policy",
        title="aws.iam.attach_role_policy",
        consequence=Consequence.DO,
        binding="aws_iam_attach_role_policy",
    ),
    Capability(
        iri="urn:gymact:multicloud:aws:capability:iam.list_roles",
        title="aws.iam.list_roles",
        consequence=Consequence.READ,
        binding="aws_iam_list_roles",
    ),
    Capability(
        iri="urn:gymact:multicloud:aws:capability:s3.create_bucket",
        title="aws.s3.create_bucket",
        consequence=Consequence.DO,
        binding="aws_s3_create_bucket",
    ),
    Capability(
        iri="urn:gymact:multicloud:aws:capability:s3.list_buckets",
        title="aws.s3.list_buckets",
        consequence=Consequence.READ,
        binding="aws_s3_list_buckets",
    ),
    Capability(
        iri="urn:gymact:multicloud:aws:capability:ec2.run_instances",
        title="aws.ec2.run_instances",
        consequence=Consequence.DO,
        binding="aws_ec2_run_instances",
    ),
    Capability(
        iri="urn:gymact:multicloud:aws:capability:ec2.describe_instances",
        title="aws.ec2.describe_instances",
        consequence=Consequence.READ,
        binding="aws_ec2_describe_instances",
    ),
    # -- Azure (azure-sdk-for-python-style operation names) -------------
    Capability(
        iri="urn:gymact:multicloud:azure:capability:authorization.create_role_assignment",
        title="azure.authorization.create_role_assignment",
        consequence=Consequence.DO,
        binding="azure_authorization_create_role_assignment",
    ),
    Capability(
        iri="urn:gymact:multicloud:azure:capability:authorization.list_role_assignments",
        title="azure.authorization.list_role_assignments",
        consequence=Consequence.READ,
        binding="azure_authorization_list_role_assignments",
    ),
    Capability(
        iri="urn:gymact:multicloud:azure:capability:storage.create_account",
        title="azure.storage.create_account",
        consequence=Consequence.DO,
        binding="azure_storage_create_account",
    ),
    Capability(
        iri="urn:gymact:multicloud:azure:capability:storage.list_accounts",
        title="azure.storage.list_accounts",
        consequence=Consequence.READ,
        binding="azure_storage_list_accounts",
    ),
    Capability(
        iri="urn:gymact:multicloud:azure:capability:compute.create_virtual_machine",
        title="azure.compute.create_virtual_machine",
        consequence=Consequence.DO,
        binding="azure_compute_create_virtual_machine",
    ),
    Capability(
        iri="urn:gymact:multicloud:azure:capability:compute.list_virtual_machines",
        title="azure.compute.list_virtual_machines",
        consequence=Consequence.READ,
        binding="azure_compute_list_virtual_machines",
    ),
    # -- GCP (google-cloud-python-style operation names) -----------------
    Capability(
        iri="urn:gymact:multicloud:gcp:capability:iam.create_service_account",
        title="gcp.iam.create_service_account",
        consequence=Consequence.DO,
        binding="gcp_iam_create_service_account",
    ),
    Capability(
        iri="urn:gymact:multicloud:gcp:capability:iam.add_iam_policy_binding",
        title="gcp.iam.add_iam_policy_binding",
        consequence=Consequence.DO,
        binding="gcp_iam_add_iam_policy_binding",
    ),
    Capability(
        iri="urn:gymact:multicloud:gcp:capability:iam.list_service_accounts",
        title="gcp.iam.list_service_accounts",
        consequence=Consequence.READ,
        binding="gcp_iam_list_service_accounts",
    ),
    Capability(
        iri="urn:gymact:multicloud:gcp:capability:storage.create_bucket",
        title="gcp.storage.create_bucket",
        consequence=Consequence.DO,
        binding="gcp_storage_create_bucket",
    ),
    Capability(
        iri="urn:gymact:multicloud:gcp:capability:storage.list_buckets",
        title="gcp.storage.list_buckets",
        consequence=Consequence.READ,
        binding="gcp_storage_list_buckets",
    ),
    Capability(
        iri="urn:gymact:multicloud:gcp:capability:compute.create_instance",
        title="gcp.compute.create_instance",
        consequence=Consequence.DO,
        binding="gcp_compute_create_instance",
    ),
    Capability(
        iri="urn:gymact:multicloud:gcp:capability:compute.list_instances",
        title="gcp.compute.list_instances",
        consequence=Consequence.READ,
        binding="gcp_compute_list_instances",
    ),
)

_BY_BINDING: dict[str, Capability] = {capability.binding: capability for capability in CAPABILITY_REGISTRY}


def _require(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"payload.{key} must be a non-empty string")
    return value


def _empty_state() -> dict[str, Any]:
    return {
        "aws": {
            "iam_roles": {},
            "iam_role_policy_attachments": {},
            "storage_buckets": {},
            "compute_instances": {},
        },
        "azure": {
            "iam_role_assignments": {},
            "storage_accounts": {},
            "compute_instances": {},
        },
        "gcp": {
            "iam_service_accounts": {},
            "iam_policy_bindings": {},
            "storage_buckets": {},
            "compute_instances": {},
        },
    }


class MulticloudEnvironment:
    """SIMULATED multicloud world: one in-memory state namespace per cloud.

    No network calls, no credentials, no real cloud API of any kind -- see
    the module docstring for the full simulation boundary.
    """

    def __init__(self, *, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:gymact:multicloud:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._state: dict[str, Any] = _empty_state()
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return CAPABILITY_REGISTRY

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = deepcopy(self._state)
        binding = capability.binding
        handler = _ACTUATORS.get(binding)
        if handler is None:
            raise ValueError(f"unsupported provider binding: {binding}")
        result = handler(self._state, payload)
        return {
            "before": before,
            "after": deepcopy(self._state),
            "capability": capability.iri,
            "result": result,
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._state = deepcopy(checkpoint)

    async def teardown(self) -> None:
        self._closed = True


# ---------------------------------------------------------------------------
# Dispatch table: one handler per Capability.binding. DO handlers mutate
# `state` in place and return the created/attached resource's real
# (simulated) descriptor. READ handlers return a real snapshot of the
# relevant sub-namespace; they are never reachable through
# `gymact.kernel.GymAct.act` (the runtime refuses to actuate a READ
# capability), but are implemented here for structural completeness --
# `MulticloudEnvironment.actuate` is a plain dispatch table with no
# authority logic of its own, so both consequence classes go through it.
# ---------------------------------------------------------------------------


def _aws_iam_create_role(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    role_name = _require(payload, "role_name")
    roles = state["aws"]["iam_roles"]
    if role_name in roles:
        raise ValueError(f"aws iam role already exists: {role_name}")
    entry = {
        "role_name": role_name,
        "arn": f"arn:aws:iam::{_AWS_ACCOUNT_ID}:role/{role_name}",
    }
    roles[role_name] = entry
    return entry


def _aws_iam_attach_role_policy(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    role_name = _require(payload, "role_name")
    policy_arn = _require(payload, "policy_arn")
    if role_name not in state["aws"]["iam_roles"]:
        raise ValueError(f"aws iam role does not exist: {role_name}")
    attachments = state["aws"]["iam_role_policy_attachments"].setdefault(role_name, [])
    if policy_arn not in attachments:
        attachments.append(policy_arn)
    return {"role_name": role_name, "policy_arn": policy_arn}


def _aws_iam_list_roles(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    return deepcopy(state["aws"]["iam_roles"])


def _aws_s3_create_bucket(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    bucket_name = _require(payload, "bucket_name")
    buckets = state["aws"]["storage_buckets"]
    if bucket_name in buckets:
        raise ValueError(f"aws s3 bucket already exists: {bucket_name}")
    entry = {"bucket_name": bucket_name, "arn": f"arn:aws:s3:::{bucket_name}"}
    buckets[bucket_name] = entry
    return entry


def _aws_s3_list_buckets(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    return deepcopy(state["aws"]["storage_buckets"])


def _aws_ec2_run_instances(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    instance_type = payload.get("instance_type", "t3.micro")
    if not isinstance(instance_type, str) or not instance_type:
        raise ValueError("payload.instance_type must be a non-empty string")
    instance_id = f"i-{uuid4().hex[:17]}"
    entry = {
        "instance_id": instance_id,
        "instance_type": instance_type,
        "arn": f"arn:aws:ec2:{_AWS_REGION}:{_AWS_ACCOUNT_ID}:instance/{instance_id}",
    }
    state["aws"]["compute_instances"][instance_id] = entry
    return entry


def _aws_ec2_describe_instances(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    return deepcopy(state["aws"]["compute_instances"])


def _azure_authorization_create_role_assignment(
    state: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    principal_id = _require(payload, "principal_id")
    role_definition = _require(payload, "role_definition")
    assignment_id = uuid4().hex
    resource_id = (
        f"/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
        f"/providers/Microsoft.Authorization/roleAssignments/{assignment_id}"
    )
    entry = {
        "id": resource_id,
        "principal_id": principal_id,
        "role_definition": role_definition,
    }
    state["azure"]["iam_role_assignments"][assignment_id] = entry
    return entry


def _azure_authorization_list_role_assignments(
    state: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    return deepcopy(state["azure"]["iam_role_assignments"])


def _azure_storage_create_account(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    account_name = _require(payload, "account_name")
    accounts = state["azure"]["storage_accounts"]
    if account_name in accounts:
        raise ValueError(f"azure storage account already exists: {account_name}")
    entry = {
        "account_name": account_name,
        "id": (
            f"/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
            f"/resourceGroups/{_AZURE_RESOURCE_GROUP}"
            f"/providers/Microsoft.Storage/storageAccounts/{account_name}"
        ),
    }
    accounts[account_name] = entry
    return entry


def _azure_storage_list_accounts(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    return deepcopy(state["azure"]["storage_accounts"])


def _azure_compute_create_virtual_machine(
    state: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    vm_name = _require(payload, "vm_name")
    instances = state["azure"]["compute_instances"]
    if vm_name in instances:
        raise ValueError(f"azure virtual machine already exists: {vm_name}")
    entry = {
        "vm_name": vm_name,
        "id": (
            f"/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
            f"/resourceGroups/{_AZURE_RESOURCE_GROUP}"
            f"/providers/Microsoft.Compute/virtualMachines/{vm_name}"
        ),
    }
    instances[vm_name] = entry
    return entry


def _azure_compute_list_virtual_machines(
    state: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    return deepcopy(state["azure"]["compute_instances"])


def _gcp_iam_create_service_account(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    account_id = _require(payload, "account_id")
    accounts = state["gcp"]["iam_service_accounts"]
    if account_id in accounts:
        raise ValueError(f"gcp service account already exists: {account_id}")
    entry = {
        "account_id": account_id,
        "email": f"{account_id}@{_GCP_PROJECT_ID}.iam.gserviceaccount.com",
        "name": f"projects/{_GCP_PROJECT_ID}/serviceAccounts/{account_id}@{_GCP_PROJECT_ID}.iam.gserviceaccount.com",
    }
    accounts[account_id] = entry
    return entry


def _gcp_iam_add_iam_policy_binding(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    member = _require(payload, "member")
    role = _require(payload, "role")
    bindings = state["gcp"]["iam_policy_bindings"].setdefault(role, [])
    if member not in bindings:
        bindings.append(member)
    return {"role": role, "member": member}


def _gcp_iam_list_service_accounts(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    return deepcopy(state["gcp"]["iam_service_accounts"])


def _gcp_storage_create_bucket(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    bucket_name = _require(payload, "bucket_name")
    buckets = state["gcp"]["storage_buckets"]
    if bucket_name in buckets:
        raise ValueError(f"gcp storage bucket already exists: {bucket_name}")
    entry = {
        "bucket_name": bucket_name,
        "name": f"projects/_/buckets/{bucket_name}",
    }
    buckets[bucket_name] = entry
    return entry


def _gcp_storage_list_buckets(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    return deepcopy(state["gcp"]["storage_buckets"])


def _gcp_compute_create_instance(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    instance_name = _require(payload, "instance_name")
    zone = payload.get("zone", _GCP_DEFAULT_ZONE)
    if not isinstance(zone, str) or not zone:
        raise ValueError("payload.zone must be a non-empty string")
    instances = state["gcp"]["compute_instances"]
    if instance_name in instances:
        raise ValueError(f"gcp compute instance already exists: {instance_name}")
    entry = {
        "instance_name": instance_name,
        "zone": zone,
        "name": f"projects/{_GCP_PROJECT_ID}/zones/{zone}/instances/{instance_name}",
    }
    instances[instance_name] = entry
    return entry


def _gcp_compute_list_instances(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    return deepcopy(state["gcp"]["compute_instances"])


_ACTUATORS = {
    "aws_iam_create_role": _aws_iam_create_role,
    "aws_iam_attach_role_policy": _aws_iam_attach_role_policy,
    "aws_iam_list_roles": _aws_iam_list_roles,
    "aws_s3_create_bucket": _aws_s3_create_bucket,
    "aws_s3_list_buckets": _aws_s3_list_buckets,
    "aws_ec2_run_instances": _aws_ec2_run_instances,
    "aws_ec2_describe_instances": _aws_ec2_describe_instances,
    "azure_authorization_create_role_assignment": _azure_authorization_create_role_assignment,
    "azure_authorization_list_role_assignments": _azure_authorization_list_role_assignments,
    "azure_storage_create_account": _azure_storage_create_account,
    "azure_storage_list_accounts": _azure_storage_list_accounts,
    "azure_compute_create_virtual_machine": _azure_compute_create_virtual_machine,
    "azure_compute_list_virtual_machines": _azure_compute_list_virtual_machines,
    "gcp_iam_create_service_account": _gcp_iam_create_service_account,
    "gcp_iam_add_iam_policy_binding": _gcp_iam_add_iam_policy_binding,
    "gcp_iam_list_service_accounts": _gcp_iam_list_service_accounts,
    "gcp_storage_create_bucket": _gcp_storage_create_bucket,
    "gcp_storage_list_buckets": _gcp_storage_list_buckets,
    "gcp_compute_create_instance": _gcp_compute_create_instance,
    "gcp_compute_list_instances": _gcp_compute_list_instances,
}

assert set(_ACTUATORS) == set(_BY_BINDING), "every capability binding must have a dispatch handler"


class MulticloudProvider:
    """Factory for isolated `MulticloudEnvironment` instances.

    Materialization itself is never authority-gated (`materialization_requires_authority
    = False`, matching `MemoryProvider`'s convention) -- only DO capability
    actuation inside a materialized environment is, via
    `MulticloudEnvironment.requires_authority` (default `True`).
    """

    name = "multicloud"
    materialization_requires_authority = False

    def __init__(self, *, requires_authority: bool = True) -> None:
        self.requires_authority = requires_authority

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> MulticloudEnvironment:
        del scenario
        configured = config.get("requires_authority", self.requires_authority)
        if not isinstance(configured, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return MulticloudEnvironment(requires_authority=configured)
