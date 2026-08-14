"""Ontology-owned semantic adapter over SREGym's real vendor physics.

The underlying ``gymact.gyms.sregym`` module owns transport/process physics.
Capability identity, consequence classification, and MCP route/tool bindings are
manufactured from ``ggen/sregym-e2e-pack/ontology.ttl`` into the generated
catalog.  This adapter is the registered provider so stale hand-authored
capability metadata in the physics module cannot become runtime standing.
"""
from __future__ import annotations

from typing import Any

from gymact.generated.sregym_mcp_catalog import SREGYM_CAPABILITY_ROWS
from gymact.gyms.sregym import SregymVendorProvider
from gymact.models import Capability, Consequence

SREGYM_CAPABILITIES = tuple(
    Capability(
        iri=row["iri"],
        title=row["title"],
        consequence=Consequence(row["consequence"]),
        binding=row["binding"],
    )
    for row in SREGYM_CAPABILITY_ROWS
)

_CAPABILITIES_BY_IRI = {capability.iri: capability for capability in SREGYM_CAPABILITIES}
_CAPABILITIES_BY_BINDING = {capability.binding: capability for capability in SREGYM_CAPABILITIES}

if len(_CAPABILITIES_BY_IRI) != len(SREGYM_CAPABILITIES):
    raise RuntimeError("SREGYM_ONTOLOGY_DUPLICATE_CAPABILITY_IRI")
if len(_CAPABILITIES_BY_BINDING) != len(SREGYM_CAPABILITIES):
    raise RuntimeError("SREGYM_ONTOLOGY_DUPLICATE_CAPABILITY_BINDING")


class OntologySregymEnvironment:
    """Delegates real SREGym physics while exposing ontology-owned capabilities."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.environment_id = inner.environment_id
        self.requires_authority = inner.requires_authority

    def capabilities(self) -> tuple[Capability, ...]:
        return SREGYM_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        return await self._inner.observe()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        admitted = _CAPABILITIES_BY_IRI.get(capability.iri)
        if admitted is None:
            raise ValueError(f"SREGYM_ONTOLOGY_UNKNOWN_CAPABILITY:{capability.iri}")
        if admitted.binding != capability.binding:
            raise ValueError(
                f"SREGYM_ONTOLOGY_BINDING_MISMATCH:{capability.iri}:"
                f"expected={admitted.binding},observed={capability.binding}"
            )
        if admitted.consequence is not capability.consequence:
            raise ValueError(
                f"SREGYM_ONTOLOGY_CONSEQUENCE_MISMATCH:{capability.iri}:"
                f"expected={admitted.consequence},observed={capability.consequence}"
            )
        # The vendor environment dispatches by binding; it does not use the
        # historical consequence bit to choose transport.  Passing the
        # ontology-owned Capability therefore preserves real physics while the
        # kernel's read()/act() split owns consequence routing.
        return await self._inner.actuate(admitted, payload)

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        return await self._inner.verify(expected)

    async def checkpoint(self) -> dict[str, Any]:
        return await self._inner.checkpoint()

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        await self._inner.restore(checkpoint)

    async def teardown(self) -> None:
        await self._inner.teardown()


class SregymOntologyProvider:
    """Registered SREGym provider: ontology semantics over exact vendor physics."""

    name = "sregym"
    materialization_requires_authority = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._physics = SregymVendorProvider(*args, **kwargs)
        self.materialization_requires_authority = bool(
            getattr(self._physics, "materialization_requires_authority", True)
        )

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> OntologySregymEnvironment:
        inner = await self._physics.materialize(scenario=scenario, config=config)
        return OntologySregymEnvironment(inner)
