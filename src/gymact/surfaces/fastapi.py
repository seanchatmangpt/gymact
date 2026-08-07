"""FastAPI surface over one GymAct runtime."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from gymact.models import ActuationIntent, CreateEpisodeRequest, RestoreRequest, VerifyRequest
from gymact.providers import MemoryProvider
from gymact.runtime import GymAct


def _runtime(runtime: GymAct | None) -> GymAct:
    if runtime is not None:
        return runtime
    instance = GymAct()
    instance.register_provider(MemoryProvider())
    return instance


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

    @app.get("/providers")
    async def providers() -> dict[str, tuple[str, ...]]:
        return {"providers": service.discover()}

    @app.post("/episodes")
    async def create_episode(request: CreateEpisodeRequest) -> dict[str, object]:
        try:
            episode = await service.create_episode(
                request.provider, scenario=request.scenario, config=request.config
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return episode.model_dump(mode="json")

    @app.get("/episodes/{episode_id}/observations/latest")
    async def observe(episode_id: str) -> dict[str, object]:
        try:
            return (await service.observe(episode_id)).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/episodes/{episode_id}/actions")
    async def act(episode_id: str, intent: ActuationIntent) -> dict[str, object]:
        if intent.episode_id != episode_id:
            raise HTTPException(status_code=409, detail="episode_id path/body mismatch")
        try:
            return (await service.act(intent)).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/episodes/{episode_id}/verify")
    async def verify(episode_id: str, request: VerifyRequest) -> dict[str, object]:
        try:
            result = await service.verify(episode_id, request.expected)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return result.model_dump(mode="json")

    @app.get("/episodes/{episode_id}/checkpoint")
    async def checkpoint(episode_id: str) -> dict[str, object]:
        try:
            return {"checkpoint": await service.checkpoint(episode_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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
