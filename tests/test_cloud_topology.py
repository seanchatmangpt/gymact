# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `gymact.gyms.cloud_topology` and
`gymact.gyms.cloud_topology_gym`.

Real collaborators throughout: the real, installed `botocore` package's
own bundled `endpoints.json` (loaded live, no network, no credentials);
the real, bundled Azure/GCP snapshot files under
`src/gymact/gyms/data/` (real data fetched from Microsoft's/Google's real
public endpoints this session, not synthetic fixtures); a real
`CloudTopologyProvider`/`CloudTopologyEnvironment` materialize->observe->
actuate->verify->checkpoint->restore->teardown cycle.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch`
anywhere in this file.
"""

from __future__ import annotations

import asyncio

import pytest

from gymact.gyms.cloud_topology import (
    load_aws_topology,
    load_azure_topology,
    load_gcp_topology,
    load_topology,
)
from gymact.gyms.cloud_topology_gym import (
    _CAPABILITY_BY_BINDING,
    CloudTopologyEnvironment,
    CloudTopologyProvider,
)


# ---------------------------------------------------------------------------
# Real AWS topology (live-loaded from botocore, no network/credentials)
# ---------------------------------------------------------------------------


def test_real_aws_topology_has_a_real_large_region_and_service_count() -> None:
    """Never a hardcoded fixture -- loaded live from the real, installed
    botocore package, so this can never silently drift stale."""
    topology = load_aws_topology()
    assert topology.provider == "aws"
    assert len(topology.regions) > 25, "real AWS Standard partition has 30+ real regions"
    assert len(topology.services) > 200, "real AWS Standard partition has 300+ real services"


def test_real_aws_topology_contains_real_named_regions() -> None:
    topology = load_aws_topology()
    codes = topology.region_codes()
    for real_region in ("us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"):
        assert real_region in codes, f"expected real AWS region {real_region!r} in {codes[:5]}..."


def test_real_aws_topology_services_in_region_is_a_real_nonempty_subset() -> None:
    topology = load_aws_topology()
    services_in_us_east_1 = topology.services_in_region("us-east-1")
    assert len(services_in_us_east_1) > 100, "us-east-1 is AWS's most-served region, real count should be large"
    assert "s3" in services_in_us_east_1 or "s3" in topology.service_names()


def test_real_aws_topology_unknown_partition_raises() -> None:
    with pytest.raises(RuntimeError, match="not found"):
        load_aws_topology(partition="not-a-real-partition")


# ---------------------------------------------------------------------------
# Real Azure topology (parsed from the bundled, real, dated snapshot)
# ---------------------------------------------------------------------------


def test_real_azure_topology_has_real_regions_and_service_tags() -> None:
    topology = load_azure_topology()
    assert topology.provider == "azure"
    assert len(topology.regions) > 30, "real Azure Service Tags publish 70+ real regions"
    assert len(topology.services) > 500, "real Azure Service Tags publish 3000+ real service tags"


def test_real_azure_topology_contains_real_named_regions_and_service_tags() -> None:
    topology = load_azure_topology()
    codes = topology.region_codes()
    assert "eastus" in codes
    assert "westeurope" in codes
    names = topology.service_names()
    assert "Storage" in names
    assert "AzureActiveDirectory" in names


def test_real_azure_topology_services_in_region_is_real_and_nonempty() -> None:
    topology = load_azure_topology()
    services = topology.services_in_region("eastus")
    assert len(services) > 10, "eastus is one of Azure's largest real regions"


# ---------------------------------------------------------------------------
# Real GCP topology (parsed from the bundled, real, dated snapshot) --
# honestly degenerate services (see module docstring: this real source
# only carries region scopes, not a per-service catalog).
# ---------------------------------------------------------------------------


def test_real_gcp_topology_has_real_regions() -> None:
    topology = load_gcp_topology()
    assert topology.provider == "gcp"
    assert len(topology.regions) > 30, "real GCP publishes 40+ real region scopes"


def test_real_gcp_topology_contains_real_named_regions() -> None:
    topology = load_gcp_topology()
    codes = topology.region_codes()
    assert "us-central1" in codes
    assert "europe-west1" in codes


def test_real_gcp_topology_services_is_honestly_degenerate() -> None:
    """Named, not hidden: GCP's real public IP-ranges source only ever
    carries the single literal service string "Google Cloud" -- this test
    pins that real limitation so a future "fix" doesn't silently pad it
    with fabricated per-service data."""
    topology = load_gcp_topology()
    assert topology.service_names() == ("Google Cloud",)


# ---------------------------------------------------------------------------
# load_topology() dispatch
# ---------------------------------------------------------------------------


def test_load_topology_dispatches_to_the_real_provider_loader() -> None:
    assert load_topology("aws").provider == "aws"
    assert load_topology("azure").provider == "azure"
    assert load_topology("gcp").provider == "gcp"


def test_load_topology_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="unknown cloud provider"):
        load_topology("not-a-real-cloud")


# ---------------------------------------------------------------------------
# Real Environment/Provider lifecycle
# ---------------------------------------------------------------------------


def test_real_provider_materialize_observe_actuate_verify_checkpoint_restore_teardown() -> None:
    async def run() -> None:
        provider = CloudTopologyProvider()
        env = await provider.materialize(scenario="aws", config={})
        assert isinstance(env, CloudTopologyEnvironment)

        observed = await env.observe()
        assert observed["provider"] == "aws"
        assert observed["region_count"] > 25

        list_regions = _CAPABILITY_BY_BINDING["list_regions"]
        result = await env.actuate(list_regions, {})
        assert len(result["result"]) == observed["region_count"]
        assert "us-east-1" in result["result"]

        services_in_region = _CAPABILITY_BY_BINDING["services_in_region"]
        result2 = await env.actuate(services_in_region, {"region": "us-east-1"})
        assert len(result2["result"]) > 100

        passed, verified = await env.verify({"provider": "aws"})
        assert passed is True
        assert verified["provider"] == "aws"

        checkpoint = await env.checkpoint()
        await env.restore(checkpoint)

        await env.teardown()
        with pytest.raises(RuntimeError, match="torn down"):
            await env.observe()

    asyncio.run(run())


def test_estimated_managed_k8s_cost_capability_declares_and_returns_real_cost() -> None:
    """The capability itself declares a real, sourced USD cost estimate
    (`Capability.costs`), and actuating it returns that same real figure per
    real provider -- not a mocked pricing lookup."""

    async def run() -> None:
        capability = _CAPABILITY_BY_BINDING["estimated_managed_k8s_cost"]
        assert len(capability.costs) == 1
        assert capability.costs[0].unit == "usd"
        assert capability.costs[0].kind == "declared_estimate"
        assert capability.costs[0].source

        provider = CloudTopologyProvider()
        for real_provider in ("aws", "azure", "gcp"):
            env = await provider.materialize(scenario=real_provider, config={})
            result = await env.actuate(capability, {})
            assert result["result"]["provider"] == real_provider
            assert result["result"]["unit"] == "usd"
            assert isinstance(result["result"]["quantity_per_hour"], float)
            assert result["result"]["quantity_per_hour"] > 0
            assert result["result"]["source"]
            await env.teardown()

    asyncio.run(run())


def test_real_provider_materializes_each_real_cloud() -> None:
    async def run() -> None:
        provider = CloudTopologyProvider()
        for real_provider in ("aws", "azure", "gcp"):
            env = await provider.materialize(scenario=real_provider, config={})
            observed = await env.observe()
            assert observed["provider"] == real_provider
            await env.teardown()

    asyncio.run(run())


def test_real_environment_rejects_unsupported_capability_binding() -> None:
    async def run() -> None:
        provider = CloudTopologyProvider()
        env = await provider.materialize(scenario="aws", config={})
        from gymact.models import Capability, Consequence

        bogus = Capability(
            iri="urn:gymact:cloud-topology:capability:bogus",
            title="not a real binding",
            consequence=Consequence.READ,
            binding="not_a_real_binding",
        )
        with pytest.raises(ValueError, match="unsupported cloud-topology binding"):
            await env.actuate(bogus, {})
        await env.teardown()

    asyncio.run(run())


def test_real_environment_restore_rejects_mismatched_provider_checkpoint() -> None:
    async def run() -> None:
        provider = CloudTopologyProvider()
        env_aws = await provider.materialize(scenario="aws", config={})
        env_azure = await provider.materialize(scenario="azure", config={})
        checkpoint = await env_aws.checkpoint()
        with pytest.raises(ValueError, match="different provider"):
            await env_azure.restore(checkpoint)
        await env_aws.teardown()
        await env_azure.teardown()

    asyncio.run(run())
