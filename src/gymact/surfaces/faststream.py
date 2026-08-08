"""FastStream binding for event-driven GymAct commands."""
from __future__ import annotations

from typing import Any

from faststream import FastStream

from gymact.brce import BRCEBroker, BrokerRequest
from gymact.models import ActuationIntent, MaterializationIntent
from gymact.providers import MemoryProvider
from gymact.runtime import GymAct, ProductionGymAct
from gymact.transport import TransportKind, normalize_candidate


def _runtime(runtime: GymAct | None) -> GymAct:
    if runtime is not None:
        return runtime
    instance = ProductionGymAct()
    instance.register_provider(MemoryProvider())
    return instance


async def dispatch_stream_command(service: GymAct, command: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one broker-neutral command; production DO traverses BRCE."""
    operation = command.get("operation")
    if operation == "discover":
        return {"operation": operation, "providers": list(service.discover())}
    if operation == "prepare_candidate":
        envelope = normalize_candidate(TransportKind.A2A, command["candidate"])
        return {
            "operation": operation,
            "result": {
                "semantic_key": envelope.semantic_key(),
                "prepared": envelope.prepared().model_dump(mode="json"),
            },
        }
    if operation == "create_episode":
        values: dict[str, Any] = {
            "provider": str(command.get("provider", "memory")),
            "scenario": command.get("scenario"),
            "config": command.get("config") or {},
            "authority_ref": command.get("authority_ref"),
        }
        if command.get("idempotency_key") is not None:
            values["idempotency_key"] = command["idempotency_key"]
        result = await service.materialize(MaterializationIntent.model_validate(values))
        return {"operation": operation, "result": result.model_dump(mode="json")}
    if operation == "capabilities":
        values = service.capabilities(str(command["episode_id"]))
        return {
            "operation": operation,
            "result": [item.model_dump(mode="json") for item in values],
        }
    if operation == "observe":
        result = await service.observe(str(command["episode_id"]))
        return {"operation": operation, "result": result.model_dump(mode="json")}
    if operation == "execute_admitted":
        request = BrokerRequest.model_validate(command["request"])
        if request.prepared.episode_id != str(command["episode_id"]):
            raise ValueError("EPISODE_ID_PATH_BODY_MISMATCH")
        result = await BRCEBroker(service).execute(request)
        return {"operation": operation, "result": result.model_dump(mode="json")}
    if operation == "act":
        intent = ActuationIntent.model_validate(command["intent"])
        result = await service.act(intent)
        return {"operation": operation, "result": result.model_dump(mode="json")}
    if operation == "verify":
        result = await service.verify(str(command["episode_id"]), command.get("expected") or {})
        return {"operation": operation, "result": result.model_dump(mode="json")}
    if operation == "checkpoint":
        result = await service.checkpoint(str(command["episode_id"]))
        return {"operation": operation, "result": {"checkpoint": result}}
    if operation == "restore":
        result = await service.restore(
            str(command["episode_id"]),
            command.get("checkpoint") or {},
            authority_ref=command.get("authority_ref"),
        )
        return {"operation": operation, "result": result.model_dump(mode="json")}
    if operation == "teardown":
        result = await service.teardown(
            str(command["episode_id"]), authority_ref=command.get("authority_ref")
        )
        return {"operation": operation, "result": result.model_dump(mode="json")}
    raise ValueError(f"unsupported stream operation: {operation}")


def bind_stream_handlers(
    broker: Any,
    runtime: GymAct | None = None,
    *,
    command_channel: str = "gymact.commands",
    event_channel: str = "gymact.events",
) -> None:
    """Register GymAct handlers on any FastStream-compatible broker."""
    service = _runtime(runtime)

    @broker.subscriber(command_channel)
    @broker.publisher(event_channel)
    async def handle(command: dict[str, Any]) -> dict[str, Any]:
        return await dispatch_stream_command(service, command)


def create_stream_app(
    broker: Any | None = None,
    runtime: GymAct | None = None,
    *,
    command_channel: str = "gymact.commands",
    event_channel: str = "gymact.events",
) -> FastStream:
    """Create a FastStream app and optionally bind a real externally chosen broker."""
    if broker is None:
        return FastStream()
    bind_stream_handlers(
        broker,
        runtime,
        command_channel=command_channel,
        event_channel=event_channel,
    )
    return FastStream(broker)
