"""FastAPI surface over one GymAct runtime."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Response

from gymact.brce import BRCEBroker, BrokerRequest
from gymact.contract import build_contract
from gymact.models import ActuationIntent, MaterializationIntent, RestoreRequest, VerifyRequest
from gymact.providers import MemoryProvider
from gymact.runtime import BoundaryBlocked, GymAct
from gymact.transport import TransportKind, normalize_candidate


def _runtime(runtime: GymAct | None) -> GymAct:
    if runtime is not None:
        return runtime
    instance = GymAct()
    instance.register_provider(MemoryProvider())
    return instance


def _boundary_error(exc: BoundaryBlocked) -> HTTPException:
    return HTTPException(status_code=503, detail={"standing": "BLOCKED", "reason": exc.code})


def create_app(runtime: GymAct | None = None) -> FastAPI:
    """Create an HTTP/OpenAPI projection without changing GymAct semantics."""
    service = _runtime(runtime)
    broker = BRCEBroker(service)
    contract = build_contract()
    app = FastAPI(title="GymAct", version="26.8.7")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ALIVE",
            "version": "26.8.7",
            "contract_digest": contract.contract_digest,
        }

    @app.get("/profile")
    async def profile() -> dict[str, object]:
        return service.profile.validate().model_dump(mode="json")

    @app.get("/contract")
    async def runtime_contract() -> dict[str, object]:
        return contract.model_dump(mode="json")

    @app.get("/evidence")
    async def evidence() -> dict[str, object]:
        return {
            "verified": service.verify_evidence_chain(),
            "records": [record.model_dump(mode="json") for record in service.evidence_records()],
        }

    @app.get("/evidence/prov")
    async def evidence_prov() -> Response:
        turtle = service.evidence_rdf().serialize(format="turtle")
        return Response(content=turtle, media_type="text/turtle")

    @app.get("/providers")
    async def providers() -> dict[str, tuple[str, ...]]:
        return {"providers": service.discover()}

    @app.post("/candidates")
    async def prepare_candidate(payload: dict[str, Any]) -> dict[str, object]:
        """Normalize a REST payload into a powerless candidate intent."""
        try:
            envelope = normalize_candidate(TransportKind.REST, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "semantic_key": envelope.semantic_key(),
            "prepared": envelope.prepared().model_dump(mode="json"),
        }

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
        except BoundaryBlocked as exc:
            raise _boundary_error(exc) from exc

    @app.post("/episodes/{episode_id}/actions/admitted")
    async def act_admitted(episode_id: str, request: BrokerRequest) -> dict[str, object]:
        """Production DO: require PreparedAction + ExecutionGrant and verify consequence."""
        if request.prepared.episode_id != episode_id:
            raise HTTPException(status_code=409, detail="episode_id path/body mismatch")
        try:
            transition = await broker.execute(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BoundaryBlocked as exc:
            raise _boundary_error(exc) from exc
        return transition.model_dump(mode="json")

    @app.post("/episodes/{episode_id}/actions", deprecated=True)
    async def act(episode_id: str, intent: ActuationIntent) -> dict[str, object]:
        """Compatibility runtime port. Production callers should use /actions/admitted."""
        if intent.episode_id != episode_id:
            raise HTTPException(status_code=409, detail="episode_id path/body mismatch")
        try:
            return (await service.act(intent)).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BoundaryBlocked as exc:
            raise _boundary_error(exc) from exc

    @app.post("/episodes/{episode_id}/verify")
    async def verify(episode_id: str, request: VerifyRequest) -> dict[str, object]:
        try:
            result = await service.verify(episode_id, request.expected)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BoundaryBlocked as exc:
            raise _boundary_error(exc) from exc
        return result.model_dump(mode="json")

    @app.get("/episodes/{episode_id}/checkpoint")
    async def checkpoint(episode_id: str) -> dict[str, object]:
        try:
            return {"checkpoint": await service.checkpoint(episode_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BoundaryBlocked as exc:
            raise _boundary_error(exc) from exc

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

    return app
