from __future__ import annotations

from typing import Any

from .contracts import normalize_faults, normalize_quotas
from .environment import CloudSimEnvironment
from .topology import normalize_topology


class CloudSimProvider:
    """Factory for isolated zero-network cloud-simulation worlds."""

    name = "cloudsim"
    materialization_requires_authority = False

    def __init__(self, *, requires_authority: bool = True) -> None:
        self.requires_authority = requires_authority

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> CloudSimEnvironment:
        del scenario
        configured = config.get("requires_authority", self.requires_authority)
        if not isinstance(configured, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return CloudSimEnvironment(
            topology=normalize_topology(config.get("topology")),
            quotas=normalize_quotas(config.get("quotas")),
            faults=normalize_faults(config.get("faults")),
            requires_authority=configured,
        )
