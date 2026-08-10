from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from gymact.models import Capability

from .capabilities import CAPABILITY_BY_BINDING, CLOUDSIM_CAPABILITIES, CLOUD_BY_BINDING
from .contracts import CloudOperation
from .state import CloudStateMachine


class CloudSimEnvironment:
    """Deterministic, in-memory semantic simulator for global cloud control planes."""

    def __init__(
        self,
        *,
        topology: dict[str, dict[str, list[str]]],
        quotas: dict[str, int],
        faults: dict[str, int],
        requires_authority: bool,
    ) -> None:
        self.environment_id = f"urn:gymact:cloudsim:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._machine = CloudStateMachine(topology=topology, quotas=quotas, faults=faults)
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return CLOUDSIM_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._machine.snapshot()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        if capability.binding not in CAPABILITY_BY_BINDING:
            raise ValueError(f"unsupported provider binding: {capability.binding}")
        before = self._machine.snapshot()
        if capability.binding == "cloudsim_advance_clock":
            effect = self._machine.advance_clock(payload.get("ticks", 1))
        else:
            cloud = CLOUD_BY_BINDING[capability.binding]
            effect = self._machine.apply(CloudOperation.from_payload(cloud, payload))
        return {
            "before": before,
            "after": self._machine.snapshot(),
            "capability": capability.iri,
            "result": effect,
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._machine.snapshot()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return self._machine.checkpoint()

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if not isinstance(checkpoint, dict):
            raise TypeError("checkpoint must be an object")
        self._machine.restore(deepcopy(checkpoint))

    async def teardown(self) -> None:
        self._closed = True
