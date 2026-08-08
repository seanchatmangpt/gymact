"""Explicit irreversible cut from maximal possibility closure into BRCE."""
from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    PreparedAction,
    admit_execution,
)
from gymact.brce import BRCEBroker, BrokerRequest, BrokerRuntime
from gymact.combinatorial import DecisionPhase, ExplorationResult, PossibilityGraph
from gymact.crown_runtime import VerifiedTransition
from gymact.evidence import digest
from gymact.models import FrozenModel, Receipt


class IrreversibleSelection(FrozenModel):
    graph_digest: str = Field(min_length=1)
    exploration_digest: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    morphism_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    prepared_digest: str = Field(min_length=1)
    grant_digest: str = Field(min_length=1)
    selector_ref: str = Field(min_length=1)
    basis_refs: tuple[str, ...] = ()
    selection_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def basis_refs_are_public_identifiers(self) -> Self:
        if any(":" not in reference for reference in self.basis_refs):
            raise ValueError("SELECTION_BASIS_REF_MUST_BE_ABSOLUTE")
        return self

    def verify_digest(self) -> bool:
        payload = self.model_dump(mode="json", exclude={"selection_digest"})
        return digest(payload) == self.selection_digest


class CombinatorialBrokerRequest(FrozenModel):
    """A BRCE request whose irreversible selection is content-bound to the request."""

    selection: IrreversibleSelection
    broker_request: BrokerRequest

    @model_validator(mode="after")
    def require_exact_cut_binding(self) -> Self:
        request = self.broker_request
        selection = self.selection
        if not selection.verify_digest():
            raise ValueError("IRREVERSIBLE_SELECTION_DIGEST_MISMATCH")
        if selection.action_ref != request.action.semantic_id:
            raise ValueError("IRREVERSIBLE_SELECTION_ACTION_DRIFT")
        if selection.capability_ref != request.action.capability_ref:
            raise ValueError("IRREVERSIBLE_SELECTION_CAPABILITY_DRIFT")
        if selection.subject_ref != request.prepared.subject.semantic_id:
            raise ValueError("IRREVERSIBLE_SELECTION_SUBJECT_DRIFT")
        prepared_digest = digest(request.prepared.model_dump(mode="json"))
        if selection.prepared_digest != prepared_digest:
            raise ValueError("IRREVERSIBLE_SELECTION_PREPARED_DRIFT")
        grant_digest = digest(request.grant.model_dump(mode="json"))
        if selection.grant_digest != grant_digest:
            raise ValueError("IRREVERSIBLE_SELECTION_GRANT_DRIFT")
        return self


class CombinatorialBRCEBroker:
    """Canonical production broker: maximal closure cut is mandatory before DO."""

    def __init__(self, runtime: BrokerRuntime) -> None:
        self._runtime = runtime
        self._broker = BRCEBroker(runtime)

    async def execute(self, request: CombinatorialBrokerRequest) -> VerifiedTransition:
        transition = await self._broker.execute(request.broker_request)
        source = transition.receipt
        values = source.model_dump(
            mode="python",
            exclude={
                "receipt_id",
                "occurred_at",
                "parent_receipt_ids",
                "possibility_graph_digest",
                "possibility_exploration_digest",
                "possibility_path_id",
                "possibility_morphism_id",
                "selection_digest",
                "selection_basis_refs",
            },
        )
        selection = request.selection
        receipt = Receipt(
            **values,
            possibility_graph_digest=selection.graph_digest,
            possibility_exploration_digest=selection.exploration_digest,
            possibility_path_id=selection.path_id,
            possibility_morphism_id=selection.morphism_id,
            selection_digest=selection.selection_digest,
            selection_basis_refs=selection.basis_refs,
            parent_receipt_ids=(*source.parent_receipt_ids, source.receipt_id),
        )
        self._runtime._record(receipt)
        return transition.model_copy(update={"receipt": receipt})


def select_irreversible_cut(
    graph: PossibilityGraph,
    exploration: ExplorationResult,
    *,
    path_id: str,
    morphism_id: str,
    action: ActionDefinition,
    prepared: PreparedAction,
    grant: ExecutionGrant,
    selector_ref: str,
    basis_refs: tuple[str, ...] = (),
    current_revision: str | None = None,
) -> IrreversibleSelection:
    """Select one admitted DO frontier edge from a complete bounded closure."""
    if exploration.graph_digest != graph.graph_digest:
        raise ValueError("POSSIBILITY_GRAPH_DRIFT")
    if exploration.truncated:
        reasons = ",".join(exploration.truncation_reasons)
        raise ValueError(f"IRREVERSIBLE_SELECTION_FROM_TRUNCATED_CLOSURE_REFUSED:{reasons}")
    frontier = next(
        (
            item
            for item in exploration.irreversible_frontier
            if item.path_id == path_id and item.morphism_id == morphism_id
        ),
        None,
    )
    if frontier is None:
        raise ValueError("IRREVERSIBLE_FRONTIER_EDGE_NOT_FOUND")
    if not frontier.admitted:
        raise ValueError(f"IRREVERSIBLE_FRONTIER_NOT_ADMITTED:{frontier.reason}")
    morphism = next(item for item in graph.morphisms if item.morphism_id == morphism_id)
    if morphism.phase is not DecisionPhase.DO:
        raise ValueError("SELECTED_MORPHISM_IS_NOT_DO")
    if prepared.action_ref != action.semantic_id:
        raise ValueError("SELECTION_ACTION_IDENTITY_MISMATCH")
    admission = admit_execution(
        action,
        prepared,
        grant,
        current_revision=current_revision,
    )
    if not admission.admitted:
        raise ValueError(f"SELECTION_GRANT_NOT_ADMITTED:{admission.reason}")
    exploration_digest = digest(exploration.model_dump(mode="json"))
    payload = {
        "graph_digest": graph.graph_digest,
        "exploration_digest": exploration_digest,
        "path_id": path_id,
        "morphism_id": morphism_id,
        "target_id": frontier.target_id,
        "action_ref": action.semantic_id,
        "capability_ref": action.capability_ref,
        "subject_ref": prepared.subject.semantic_id,
        "prepared_digest": digest(prepared.model_dump(mode="json")),
        "grant_digest": digest(grant.model_dump(mode="json")),
        "selector_ref": selector_ref,
        "basis_refs": basis_refs,
    }
    return IrreversibleSelection(**payload, selection_digest=digest(payload))


def manufacture_broker_request(
    selection: IrreversibleSelection,
    *,
    action: ActionDefinition,
    prepared: PreparedAction,
    grant: ExecutionGrant,
    current_revision: str | None = None,
    expected: dict[str, object] | None = None,
) -> CombinatorialBrokerRequest:
    """Manufacture BRCE request and re-check every identity bound by the cut."""
    request = BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        current_revision=current_revision,
        expected=expected or {},
    )
    return CombinatorialBrokerRequest(selection=selection, broker_request=request)
