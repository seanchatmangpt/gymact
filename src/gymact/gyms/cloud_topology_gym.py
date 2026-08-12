"""Real, read-only gym exposing `gymact.gyms.cloud_topology`'s
provider-published cloud data as a queryable `Environment` -- so an agent
with no prior cloud knowledge can ask "what regions/services does this
provider actually have" and get the real, published answer, not a
simulated approximation (see `cloud_topology.py`'s own module docstring for
why `multicloud.py`/`cloudsim` don't already provide this).

Every capability here is `Consequence.READ` -- this gym never actuates
anything; it only answers questions against the real, already-loaded
topology data. `requires_authority` defaults `False`: reading a cloud
provider's own public region/service catalog carries no real consequence
to gate.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

from .cloud_topology import CloudTopology, load_topology

CLOUD_TOPOLOGY_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        iri="urn:gymact:cloud-topology:capability:list_regions",
        title="List every real region this provider publishes (payload: {})",
        consequence=Consequence.READ,
        binding="list_regions",
    ),
    Capability(
        iri="urn:gymact:cloud-topology:capability:list_services",
        title="List every real service/service-tag this provider publishes (payload: {})",
        consequence=Consequence.READ,
        binding="list_services",
    ),
    Capability(
        iri="urn:gymact:cloud-topology:capability:services_in_region",
        title="List real services available in a given real region (payload: {'region': str})",
        consequence=Consequence.READ,
        binding="services_in_region",
    ),
)
_CAPABILITY_BY_BINDING = {c.binding: c for c in CLOUD_TOPOLOGY_CAPABILITIES}


class CloudTopologyEnvironment:
    """A materialized, real, provider-published cloud topology for one
    real provider (`"aws"`, `"azure"`, or `"gcp"`)."""

    def __init__(self, *, provider: str, requires_authority: bool = False) -> None:
        self.environment_id = f"urn:gymact:cloud-topology:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.provider = provider
        self._topology: CloudTopology = load_topology(provider)
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return CLOUD_TOPOLOGY_CAPABILITIES

    def _state(self) -> dict[str, Any]:
        return {
            "provider": self._topology.provider,
            "region_count": len(self._topology.regions),
            "service_count": len(self._topology.services),
            "source_url": self._topology.source_url,
            "source_version": self._topology.source_version,
            "fetched_at": self._topology.fetched_at,
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        if binding == "list_regions":
            result: Any = list(self._topology.region_codes())
        elif binding == "list_services":
            result = list(self._topology.service_names())
        elif binding == "services_in_region":
            region = payload.get("region")
            if not isinstance(region, str) or not region:
                raise ValueError("payload.region must be a non-empty string")
            result = list(self._topology.services_in_region(region))
        else:
            raise ValueError(f"unsupported cloud-topology binding: {binding}")
        return {
            "before": before,
            "after": self._state(),
            "capability": capability.iri,
            "result": result,
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        # The real topology is immutable once loaded (read-only gym, no
        # actuation mutates it) -- a checkpoint has nothing real to capture
        # beyond identity.
        return {"provider": self.provider}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("provider") != self.provider:
            raise ValueError("checkpoint belongs to a different provider")

    async def teardown(self) -> None:
        self._closed = True


class CloudTopologyProvider:
    """GymAct `EnvironmentProvider` materializing a real,
    provider-published `CloudTopologyEnvironment`."""

    name = "cloud-topology"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> CloudTopologyEnvironment:
        provider = scenario or config.get("provider", "aws")
        if not isinstance(provider, str):
            raise TypeError("config.provider must be a string")
        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return CloudTopologyEnvironment(provider=provider, requires_authority=requires_authority)
