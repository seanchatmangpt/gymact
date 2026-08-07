"""FastAPI surface over one GymAct runtime."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from gymact.contract import contract_document
from gymact.models import ActuationIntent, MaterializationIntent, RestoreRequest, VerifyRequest
from gymact.providers import MemoryProvider
from gymact.runtime import GymAct, GymActOperationError


def _runtime(runtime: GymAct | None) -> GymAct:
    if runtime is not None:
        return runtime
    instance = GymAct()
    instance.register_provider(MemoryProvider())
    return instance


def _raise_operation_error(exc: GymActOperationError) -> None:
    detail: dict[str, object] = {"message": str(exc)}
    if exc.receipt is not None:
        detail["receipt"] = exc.receipt.model_dump(mode="json")
    raise HTTPException(status_code=502, detail=detail) from exc


def create_app(runtime: GymAct | None = None) -> FastAPI:
    """Create an HTTP/OpenAPI projection without changing GymAct semantics."""
    service = _runtime(runtime)
    app = FastAPI(title="GymAct", version="26.8.7")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ALIVE", "version": "26.8.7"}

    @app.get("/profile")
    async def profile() -> dict[str, object]:
        return service.profile.validate().model_dump(mode="json")

    @app.get("/contract")
    async def contract() -> dict[str, object]:
        return contract_document()

    @app.get("/providers")
    async def providers() -> dict[str, tuple[str, ...]]:
        return {"providers": service.discover()}

    @app.post("/episodes")
    async def materialize(intent: MaterializationIntent) -> dict[str, object]:
        return (await service.materialize(intent)).model_dump(mode="json")

    @app.get("/episodes/{episode_id}/capabilities")
    async def capabilities(episode_id: str) -> dict[str, object]:
        try:
            values = service.capabilities(episode_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"capabilities": [item.model_dump(mode="json") for item in values]}

    @app.get("/episodes/{episode_id}/observations/latest")
    async def observe(episode_id: str) -> dict[str, object]:
        try:
            return (await service.observe(episode_id)).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GymActOperationError as exc:
            _raise_operation_error(exc)

    @app.post("/episodes/{episode_id}/actions")
    async def act(episode_id: str, intent: ActuationIntent) -> dict[str, object]:
        if intent.episode_id != episode_id:
            raise HTTPException(status_code=409, detail="episode_id path/body mismatch")
        try:
            return (await service.act(intent)).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GymActOperationError as exc:
            _raise_operation_error(exc)

    @app.post("/episodes/{episode_id}/verify")
    async def verify(episode_id: str, request: VerifyRequest) -> dict[str, object]:
        try:
            result = await service.verify(episode_id, request.expected)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GymActOperationError as exc:
            _raise_operation_error(exc)
        return result.model_dump(mode="json")

    @app.get("/episodes/{episode_id}/checkpoint")
    async def checkpoint(episode_id: str) -> dict[str, object]:
        try:
            return {"checkpoint": await service.checkpoint(episode_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GymActOperationError as exc:
            _raise_operation_error(exc)

    @app.post("/episodes/{episode_id}/restore")
    async def restore(
        episode_id: str, request: RestoreRequest, authority_ref: str | None = None
    ) -> dict[str, object]:
        try:
            result = await service.restore(
                episode_id, request.checkpoint, authority_ref=authority_ref
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return result.model_dump(mode="json")

    @app.delete("/episodes/{episode_id}")
    async def teardown(episode_id: str, authority_ref: str | None = None) -> dict[str, object]:
        try:
            result = await service.teardown(episode_id, authority_ref=authority_ref)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return result.model_dump(mode="json")

    @app.get("/episodes/{episode_id}/receipts")
    async def receipts(episode_id: str) -> dict[str, object]:
        values = await service.receipts(episode_id)
        return {"receipts": [item.model_dump(mode="json") for item in values]}

    @app.get("/evidence/prov")
    async def provenance() -> Response:
        graph = await service.provenance()
        return Response(content=graph.serialize(format="turtle"), media_type="text/turtle")

    return app
