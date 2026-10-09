"""FastAPI surface over one GymAct runtime."""

from __future__ import annotations

import hashlib
import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response

from gymact.brce import BRCEBroker, BrokerRequest
from gymact.contract import build_contract
from gymact.cut import CombinatorialBrokerRequest
from gymact.dcm_runtime import DCMDecisionCourt, DecisionCourtRequest
from gymact.models import ActuationIntent, MaterializationIntent, RestoreRequest, VerifyRequest
from gymact.providers import MemoryProvider
from gymact.runtime import BoundaryBlocked, GymAct, ProductionGymAct
from gymact.transport import TransportKind, normalize_candidate

DEFAULT_AGENT_CARD_ID = "gymact.http"
_CARDS_DIR = Path(__file__).resolve().parents[3] / "priv" / "cards"
_WELL_KNOWN_CARD_PATH = "/.well-known/agent-card.json"


class AgentCardNotConfigured(ValueError):
    """Typed refusal: the configured agent card id has no published card file."""


def published_agent_card_bytes(card_id: str) -> bytes:
    """Load the exact published card bytes for ``card_id`` from ``priv/cards/``.

    The committed card files are the court-verified artifact (determinism
    court in ``tests/test_agent_cards.py``), so the route serves their bytes
    verbatim. ``GYMACT_CARDS_DIR`` overrides the directory for deployments
    that publish cards outside the repo checkout.
    """
    cards_dir = Path(os.environ.get("GYMACT_CARDS_DIR", _CARDS_DIR))
    path = cards_dir / f"{card_id}.json"
    if not path.is_file():
        raise AgentCardNotConfigured(
            f"AGENT_CARD_NOT_CONFIGURED: no published agent card "
            f"'{card_id}' at {path} (expected priv/cards/{card_id}.json)"
        )
    return path.read_bytes()


def _runtime(runtime: GymAct | None) -> GymAct:
    if runtime is not None:
        return runtime
    instance = ProductionGymAct()
    instance.register_provider(MemoryProvider())
    return instance


def _boundary_error(exc: BoundaryBlocked) -> HTTPException:
    return HTTPException(status_code=503, detail={"standing": "BLOCKED", "reason": exc.code})


def _app_version() -> str:
    try:
        return _package_version("gymact")
    except PackageNotFoundError:
        from gymact import __version__

        return __version__


def create_app(
    runtime: GymAct | None = None,
    card_id: str | None = None,
) -> FastAPI:
    """Create HTTP/OpenAPI projection with DCM as the canonical production DO path.

    ``card_id`` selects the published agent card served at
    ``/.well-known/agent-card.json`` (default ``gymact.http``; the
    ``GYMACT_AGENT_CARD`` environment variable overrides per instance).
    A missing card file is a typed ``AgentCardNotConfigured`` refusal raised
    at app creation, never a silent 404 at request time.
    """
    service = _runtime(runtime)
    compatibility_broker = BRCEBroker(service)
    court = DCMDecisionCourt()
    contract = build_contract()
    app = FastAPI(title="GymAct", version=_app_version())

    resolved_card_id = os.environ.get("GYMACT_AGENT_CARD", "") or card_id or DEFAULT_AGENT_CARD_ID
    card_bytes = published_agent_card_bytes(resolved_card_id)
    card_etag = f'"{hashlib.sha256(card_bytes).hexdigest()[:32]}"'

    @app.get(_WELL_KNOWN_CARD_PATH)
    async def agent_card(request: Request) -> Response:
        """Serve the published agent card bytes with ETag/304 revalidation."""
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match.strip() == card_etag:
            return Response(status_code=304, headers={"ETag": card_etag})
        return Response(
            content=card_bytes,
            media_type="application/json",
            headers={"ETag": card_etag},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ALIVE",
            "version": _app_version(),
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

    @app.post("/possibilities/explore")
    async def explore_possibilities(request: DecisionCourtRequest) -> dict[str, object]:
        """Admit RDF authority and return maximal proven-reversible closure plus DO frontier."""
        try:
            return court.admit_request(request).model_dump(mode="json")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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

    @app.post("/episodes/{episode_id}/actions/selected")
    async def act_selected(
        episode_id: str,
        request: CombinatorialBrokerRequest,
    ) -> dict[str, object]:
        """Canonical DO: execute only a cut bound to maximal possibility closure."""
        if request.broker_request.prepared.episode_id != episode_id:
            raise HTTPException(status_code=409, detail="episode_id path/body mismatch")
        try:
            transition = await court.execute(service, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BoundaryBlocked as exc:
            raise _boundary_error(exc) from exc
        return transition.model_dump(mode="json")

    @app.post("/episodes/{episode_id}/actions/admitted", deprecated=True)
    async def act_admitted(episode_id: str, request: BrokerRequest) -> dict[str, object]:
        """Compatibility BRCE path; new production clients use /actions/selected."""
        if request.prepared.episode_id != episode_id:
            raise HTTPException(status_code=409, detail="episode_id path/body mismatch")
        try:
            transition = await compatibility_broker.execute(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BoundaryBlocked as exc:
            raise _boundary_error(exc) from exc
        return transition.model_dump(mode="json")

    @app.post("/episodes/{episode_id}/actions", deprecated=True)
    async def act(episode_id: str, intent: ActuationIntent) -> dict[str, object]:
        """Legacy raw port; ProductionGymAct returns a receipted refusal."""
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
        episode_id: str,
        request: RestoreRequest,
        authority_ref: str | None = None,
    ) -> dict[str, object]:
        try:
            result = await service.restore(
                episode_id,
                request.checkpoint,
                authority_ref=authority_ref,
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
