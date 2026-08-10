from __future__ import annotations

from copy import deepcopy
from typing import Any

from .capabilities import CLOUDS
from .contracts import CloudOperation, Effect


class CloudStateMachine:
    """Finite semantic kernel for an open-ended cloud control-plane operation space."""

    def __init__(
        self,
        *,
        topology: dict[str, dict[str, list[str]]],
        quotas: dict[str, int],
        faults: dict[str, int],
    ) -> None:
        self._state: dict[str, Any] = {
            "logical_clock": 0,
            "sequence": 0,
            "topology": deepcopy(topology),
            "resources": {cloud: {} for cloud in CLOUDS},
            "bindings": {cloud: [] for cloud in CLOUDS},
            "events": [],
        }
        self._quotas = dict(quotas)
        self._faults = dict(faults)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._state)

    def checkpoint(self) -> dict[str, Any]:
        return {
            "state": deepcopy(self._state),
            "quotas": dict(self._quotas),
            "faults": dict(self._faults),
        }

    def restore(self, checkpoint: dict[str, Any]) -> None:
        state = checkpoint.get("state")
        quotas = checkpoint.get("quotas")
        faults = checkpoint.get("faults")
        valid = isinstance(state, dict) and isinstance(quotas, dict) and isinstance(faults, dict)
        if not valid:
            raise ValueError("checkpoint is not a CloudSim checkpoint")
        self._state = deepcopy(state)
        self._quotas = dict(quotas)
        self._faults = dict(faults)

    def advance_clock(self, ticks: int) -> dict[str, Any]:
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks <= 0:
            raise ValueError("payload.ticks must be a positive integer")
        self._state["logical_clock"] += ticks
        self._refresh_visibility()
        event = self._event("cloudsim", "clock", "advance", {"ticks": ticks})
        return {"logical_clock": self._state["logical_clock"], "event": event}

    def apply(self, operation: CloudOperation) -> dict[str, Any]:
        self._validate_location(operation)
        self._maybe_fail(operation)
        before = deepcopy(self._state)
        try:
            self._state["sequence"] += 1
            if operation.effect is Effect.CREATE:
                return self._create(operation)
            if operation.effect is Effect.UPDATE:
                return self._update(operation)
            if operation.effect is Effect.DELETE:
                return self._delete(operation)
            if operation.effect is Effect.BIND:
                return self._bind(operation)
            if operation.effect is Effect.UNBIND:
                return self._unbind(operation)
            if operation.effect is Effect.TRANSITION:
                return self._transition(operation)
            return self._invoke(operation)
        except Exception:
            self._state = before
            raise

    def _create(self, operation: CloudOperation) -> dict[str, Any]:
        resources = self._state["resources"][operation.cloud]
        resource_id = operation.resource_id or self._resource_id(operation)
        if resource_id in resources:
            raise ValueError(f"resource already exists: {resource_id}")
        missing = [item for item in operation.depends_on if not self._resource_exists(item)]
        if missing:
            raise ValueError(f"missing dependencies: {','.join(sorted(missing))}")
        self._check_quota(operation)
        clock = self._state["logical_clock"]
        resource = {
            "id": resource_id,
            "cloud": operation.cloud,
            "service": operation.service,
            "resource_type": operation.resource_type,
            "name": operation.name,
            "scope": operation.scope,
            "region": operation.region,
            "properties": deepcopy(operation.properties),
            "depends_on": list(operation.depends_on),
            "lifecycle": "ACTIVE",
            "created_at": clock,
            "updated_at": clock,
            "visible_at": clock + operation.visibility_delay,
            "visible": operation.visibility_delay == 0,
        }
        resources[resource_id] = resource
        event = self._event(operation.cloud, operation.service, operation.operation, resource)
        return {"resource": deepcopy(resource), "event": event}

    def _update(self, operation: CloudOperation) -> dict[str, Any]:
        resource = self._require_resource(operation)
        resource["properties"].update(deepcopy(operation.properties))
        resource["updated_at"] = self._state["logical_clock"]
        event = self._event(operation.cloud, operation.service, operation.operation, resource)
        return {"resource": deepcopy(resource), "event": event}

    def _delete(self, operation: CloudOperation) -> dict[str, Any]:
        resource = self._require_resource(operation)
        resource_id = resource["id"]
        dependents = self._dependents(resource_id)
        if dependents:
            raise ValueError(f"resource has active dependents: {','.join(sorted(dependents))}")
        del self._state["resources"][operation.cloud][resource_id]
        self._state["bindings"][operation.cloud] = [
            item
            for item in self._state["bindings"][operation.cloud]
            if item["source"] != resource_id and item["target"] != resource_id
        ]
        event = self._event(
            operation.cloud,
            operation.service,
            operation.operation,
            {"resource_id": resource_id},
        )
        return {"deleted": resource_id, "event": event}

    def _bind(self, operation: CloudOperation) -> dict[str, Any]:
        source = operation.resource_id or operation.properties.get("source")
        target = operation.properties.get("target")
        relation = operation.properties.get("relation", "permission")
        if not isinstance(source, str) or not self._resource_exists(source):
            raise ValueError("binding source must reference an existing resource")
        if not isinstance(target, str) or not target:
            raise ValueError("binding target must be a non-empty string")
        if not isinstance(relation, str) or not relation:
            raise ValueError("binding relation must be a non-empty string")
        binding = {"source": source, "target": target, "relation": relation}
        bindings = self._state["bindings"][operation.cloud]
        if binding not in bindings:
            bindings.append(binding)
        event = self._event(operation.cloud, operation.service, operation.operation, binding)
        return {"binding": deepcopy(binding), "event": event}

    def _unbind(self, operation: CloudOperation) -> dict[str, Any]:
        source = operation.resource_id or operation.properties.get("source")
        target = operation.properties.get("target")
        relation = operation.properties.get("relation", "permission")
        before = len(self._state["bindings"][operation.cloud])
        self._state["bindings"][operation.cloud] = [
            item
            for item in self._state["bindings"][operation.cloud]
            if not (
                item["source"] == source
                and item["target"] == target
                and item["relation"] == relation
            )
        ]
        removed = before - len(self._state["bindings"][operation.cloud])
        event = self._event(
            operation.cloud,
            operation.service,
            operation.operation,
            {"removed": removed},
        )
        return {"removed": removed, "event": event}

    def _transition(self, operation: CloudOperation) -> dict[str, Any]:
        resource = self._require_resource(operation)
        lifecycle = operation.properties.get("lifecycle")
        if not isinstance(lifecycle, str) or not lifecycle:
            raise ValueError("TRANSITION requires properties.lifecycle")
        resource["lifecycle"] = lifecycle
        resource["updated_at"] = self._state["logical_clock"]
        event = self._event(operation.cloud, operation.service, operation.operation, resource)
        return {"resource": deepcopy(resource), "event": event}

    def _invoke(self, operation: CloudOperation) -> dict[str, Any]:
        invocation = {
            "cloud": operation.cloud,
            "service": operation.service,
            "operation": operation.operation,
            "scope": operation.scope,
            "region": operation.region,
            "properties": deepcopy(operation.properties),
        }
        event = self._event(operation.cloud, operation.service, operation.operation, invocation)
        return {"invocation": invocation, "event": event}

    def _require_resource(self, operation: CloudOperation) -> dict[str, Any]:
        resource_id = operation.resource_id
        if not resource_id:
            raise ValueError(f"{operation.effect.value} requires payload.resource_id")
        resource = self._state["resources"][operation.cloud].get(resource_id)
        if resource is None:
            raise ValueError(f"resource does not exist: {resource_id}")
        return resource

    def _resource_exists(self, resource_id: str) -> bool:
        return any(resource_id in self._state["resources"][cloud] for cloud in CLOUDS)

    def _dependents(self, resource_id: str) -> list[str]:
        result: list[str] = []
        for cloud in CLOUDS:
            for candidate_id, resource in self._state["resources"][cloud].items():
                if resource_id in resource["depends_on"]:
                    result.append(candidate_id)
        return result

    def _resource_id(self, operation: CloudOperation) -> str:
        sequence = self._state["sequence"]
        token = f"{operation.resource_type}/{operation.name}-{sequence:06d}"
        if operation.cloud == "aws":
            return f"arn:aws:{operation.service}:{operation.region}:000000000000:{token}"
        if operation.cloud == "azure":
            return (
                "/subscriptions/00000000-0000-0000-0000-000000000000"
                f"/resourceGroups/{operation.scope}/providers/GymAct.{operation.service}/{token}"
            )
        return f"projects/gymact-simulated/locations/{operation.region}/{token}"

    def _validate_location(self, operation: CloudOperation) -> None:
        topology = self._state["topology"][operation.cloud]
        if operation.scope not in topology["scopes"]:
            raise ValueError(f"scope is outside admitted topology: {operation.scope}")
        if operation.region not in topology["regions"]:
            raise ValueError(f"region is outside admitted topology: {operation.region}")

    def _check_quota(self, operation: CloudOperation) -> None:
        key = f"{operation.cloud}:{operation.service}:{operation.resource_type}"
        limit = self._quotas.get(key)
        if limit is None:
            return
        count = sum(
            1
            for item in self._state["resources"][operation.cloud].values()
            if item["service"] == operation.service
            and item["resource_type"] == operation.resource_type
        )
        if count >= limit:
            raise RuntimeError(f"quota exceeded: {key}")

    def _maybe_fail(self, operation: CloudOperation) -> None:
        key = f"{operation.cloud}:{operation.service}:{operation.operation}"
        remaining = self._faults.get(key, 0)
        if remaining <= 0:
            return
        self._faults[key] = remaining - 1
        raise RuntimeError(f"injected cloud fault: {key}")

    def _refresh_visibility(self) -> None:
        clock = self._state["logical_clock"]
        for cloud in CLOUDS:
            for resource in self._state["resources"][cloud].values():
                resource["visible"] = resource["visible_at"] <= clock

    def _event(
        self,
        cloud: str,
        service: str,
        operation: str,
        detail: dict[str, Any],
    ) -> dict[str, Any]:
        event = {
            "sequence": len(self._state["events"]) + 1,
            "clock": self._state["logical_clock"],
            "cloud": cloud,
            "service": service,
            "operation": operation,
            "detail": deepcopy(detail),
        }
        self._state["events"].append(event)
        return deepcopy(event)
